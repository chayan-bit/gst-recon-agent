"""Oracle endpoint for harness checks: an OpenAI-compatible server that answers every rendered case with
its own target.json (matched on the exact prompt.txt text). `gst_recon.eval run` against it must score 1.0.

    python -m realworld.oracle data/realworld --port 30777 &
    python -m gst_recon.eval run --endpoint http://127.0.0.1:30777/v1 --model oracle --cases data/realworld \
        --out runs/eval/realworld-oracle --truth-dir data/truth
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def serve(root: Path, port: int) -> None:
    answers = {(d / "prompt.txt").read_text(): (d / "target.json").read_text() for d in root.iterdir() if (d / "meta.json").exists()}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            user = body["messages"][-1]["content"]
            text = next((t for p, t in answers.items() if p.strip() in user), "no such case")
            out = json.dumps({"choices": [{"message": {"content": text}, "finish_reason": "stop"}],
                              "usage": {"prompt_tokens": len(user) // 4, "completion_tokens": len(text) // 4}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

    print(f"oracle: {len(answers)} cases on 127.0.0.1:{port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()


if __name__ == "__main__":
    serve(Path(sys.argv[1]), int(sys.argv[3]) if len(sys.argv) > 3 else 30777)
