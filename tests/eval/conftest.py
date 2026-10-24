"""Stub rendered cases and a stub OpenAI-compatible server (no GPU, no network)."""

from __future__ import annotations

import json
import threading
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from gst_recon.sim.world import generate_case

DIFFS = ("easy", "medium", "hard")


@lru_cache(maxsize=None)
def _cases(split: str, n: int, seed: int):
    return tuple(generate_case(seed, DIFFS[i % 3], i // 3, split=split) for i in range(n))


def make_rendered(root: Path, split: str, n: int, truth_dir: Path | None = None, seed: int = 3) -> dict[str, dict]:
    """Write <root>/<case_id>/{prompt.txt,target.json,meta.json}; prompt = case id line + truth inputs JSON."""
    targets = {}
    for i, c in enumerate(_cases(split, n, seed)):
        d = root / c.case_id
        d.mkdir(parents=True)
        (d / "prompt.txt").write_text(f"CASE_ID: {c.case_id}\n{c.inputs.model_dump_json()}")
        (d / "target.json").write_text(c.expected.model_dump_json())
        (d / "meta.json").write_text(json.dumps({"case_id": c.case_id, "difficulty": c.difficulty, "split": split,
                                                 "ocr_recall": 1.0 if i % 2 == 0 else 0.9}))
        targets[c.case_id] = c.expected.model_dump(mode="json")
        if truth_dir is not None:
            truth_dir.mkdir(parents=True, exist_ok=True)
            (truth_dir / f"{c.case_id}.json").write_text(c.model_dump_json())
    return targets


class Stub:
    def __init__(self, targets: dict[str, dict]):
        self.targets, self.requests = targets, []
        stub = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):  # noqa: D401
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                stub.requests.append(body)
                user = body["messages"][-1]["content"]
                cid = user.split("\n", 1)[0].removeprefix("CASE_ID: ")
                mode = body["model"]
                if mode == "ctx":  # server context 10000 tokens, prompt 1000: max_tokens above 8992 is a 400
                    if body["max_tokens"] > 8992:
                        self.send_response(400)
                        self.end_headers()
                        self.wfile.write(b"Requested token count exceeds the model's maximum context length of 10000 tokens. "
                                         b"You requested a total of 40000 tokens: 1000 tokens from the input messages and 32768 for the completion.")
                        return
                    mode = "perfect"
                if mode == "fail500":
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(b"boom")
                    return
                text = self._reply(mode, stub.targets[cid])
                out = json.dumps({"choices": [{"message": {"content": text}, "finish_reason": "stop"}],
                                  "usage": {"prompt_tokens": 1000, "completion_tokens": 200}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

            @staticmethod
            def _reply(mode: str, target: dict) -> str:
                if mode == "perfect":
                    return json.dumps(target)
                if mode == "fenced":
                    return "```json\n" + json.dumps(target) + "\n```"
                if mode == "garbage":
                    return "I cannot do this."
                t = json.loads(json.dumps(target))  # "noisy": wrong ITC totals, first extraction corrupted
                t["itc_totals"]["eligible"]["igst"] += 1000.0
                if t["extractions"]:
                    t["extractions"][0]["invoice_no"] = "WRONG"
                return json.dumps(t)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_port}/v1"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()


@pytest.fixture
def world(tmp_path):
    truth = tmp_path / "truth"
    targets = {}
    dirs = {}
    for split in ("test_iid", "test_ood"):
        dirs[split] = tmp_path / "rendered" / split
        targets |= make_rendered(dirs[split], split, 3, truth)
    stub = Stub(targets)
    yield {"dirs": dirs, "truth": truth, "stub": stub, "tmp": tmp_path, "targets": targets}
    stub.close()
