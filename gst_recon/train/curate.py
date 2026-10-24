"""CuratorKIT stage: teacher paraphrase with grounding gates, dedup, secret hygiene, provenance.

raw     = every generated case, every teacher rewrite applied as returned, no gates.
curated = cases whose OCR lost only line HSN codes get those blanked in the target,
          other OCR-unrecoverable cases are dropped; a rewrite is kept only if every fact
          string survives (code check) and CuratorKIT's HallucinationGate judges it
          grounded, otherwise the block keeps its original text; then CuratorKIT
          exact + MinHash dedup and SecretsGate; manifest via ProvenanceManifest.

Not used, on purpose: CuratorKIT's PIIPseudonymizer rewrites names and number-like
spans (GSTINs, invoice numbers, bank refs) that the target JSON must reproduce
verbatim, so it would corrupt labels; every identity here is synthetic by
construction (simulator GSTINs, Faker names), so there is no real PII to remove.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

from curatorkit.gates.hallucination import HallucinationGate
from curatorkit.hygiene.secrets import _PLUGINS_BASE, SecretsGate
from curatorkit.llm.litellm import LiteLLMBackend
from curatorkit.manifest import ProvenanceManifest
from curatorkit.normalizers.dedup import ExactDeduplicator, MinHashDeduplicator
from curatorkit.pipeline import PipelineResult
from curatorkit.schema import DataSample, RejectedSample

from gst_recon.train import paraphrase as para
from gst_recon.train.build import Candidate, mask_lost_hsn

GROUNDING_THRESHOLD = 0.8
MINHASH_THRESHOLD = 0.9  # shortcut: tuned on nothing yet; report removals and revisit if > 1% of cases
MINHASH_NGRAM = 12  # long char n-grams: shared JSON/table boilerplate must not make distinct cases look alike
MINHASH_PERM = 32
# shortcut: MinHash sees only the first DEDUP_CHARS of the prompt (buyer header + first documents);
# CuratorKIT's MinHash is pure Python (2.5-10 s per full 40k-char case on 2 cores at 64 perms).
# Exact dedup still sees everything. Upgrade: a vectorised MinHash if near-dups turn up past the prefix.
DEDUP_CHARS = 8000
# SecretsGate minus its entropy heuristics: with them it rejected 32% of cases, all on bank-statement
# UTR refs such as HDFCN457645932682 (digit runs count as hex), which the target must reproduce.
# The credential-format detectors (AWS, GitHub, JWT, private keys, Slack, Stripe, ...) stay on.
SECRET_PLUGINS = [p for p in _PLUGINS_BASE if "HighEntropy" not in p["name"]]


def _minhash_shard(samples: list[DataSample]) -> list[str]:
    probe = [s.model_copy(update={"instruction": s.instruction[:DEDUP_CHARS], "output": ""}) for s in samples]
    dedup = MinHashDeduplicator(threshold=MINHASH_THRESHOLD, ngram=MINHASH_NGRAM, num_perm=MINHASH_PERM)
    return [s.id for s in dedup.run(probe)]


def _minhash(samples: list[DataSample]) -> list[DataSample]:
    """Near-dup removal within each difficulty (cases of different difficulty differ in size by
    construction, so cannot be near-duplicates), one process per shard."""
    shards = [[s for s in samples if s.metadata["difficulty"] == d] for d in ("easy", "medium", "hard")]
    with ProcessPoolExecutor(len(shards)) as pool:
        keep = {i for ids in pool.map(_minhash_shard, shards) for i in ids}
    return [s for s in samples if s.id in keep]


def teacher(base_url: str, model: str, temperature: float = 0.8, max_tokens: int = 2048) -> LiteLLMBackend:
    """SGLang's OpenAI-compatible server through LiteLLM's `openai/` provider prefix."""
    return LiteLLMBackend(model=f"openai/{model}", api_base=base_url, temperature=temperature, max_tokens=max_tokens)


def _reject(sample: DataSample, reason: str, step: str) -> RejectedSample:
    return RejectedSample(**sample.model_dump(exclude={"provenance_chain"}), rejection_reason=reason,
                          rejecting_step=step)


def _extractions(c: Candidate) -> dict[str, dict]:
    return {e["doc_id"]: e for e in json.loads(c.target)["extractions"]}


def paraphrase_stage(cands: list[Candidate], gen, judge, workers: int = 32) -> tuple[dict, dict, list, dict]:
    """Rewrite every text-delivered block of the train cases.

    Returns (raw_rewrites, gated_rewrites, rejected, counts); rewrites map
    case_id -> {doc_id: text}."""
    jobs = [(c, doc, text) for c in cands if c.split == "train" for doc, _, text in para.blocks(c.prompt)]

    def run(job):
        text = job[2]
        msgs = [{"role": "system", "content": para.INSTRUCTION}, {"role": "user", "content": text}]
        try:
            text = gen.generate(msgs).text.strip()
            return "\n".join(line.rstrip() for line in text.splitlines())  # teacher pads lines with markdown breaks
        except Exception as e:  # noqa: BLE001 - one failed call must not stop the batch
            return e

    with ThreadPoolExecutor(workers) as pool:
        outs = list(pool.map(run, jobs))
    errors = [o for o in outs if isinstance(o, Exception)]
    if jobs and len(errors) == len(jobs):  # e.g. a dead tunnel: fail loudly instead of a silent no-op stage
        raise RuntimeError(f"teacher failed on all {len(jobs)} blocks: {errors[0]}") from errors[0]
    raw: dict[str, dict] = {}
    samples, rejected = [], []
    extraction = {c.case_id: _extractions(c) for c in {j[0].case_id: j[0] for j in jobs}.values()}
    for (c, doc, text), out in zip(jobs, outs):
        s = DataSample(id=f"{c.case_id}:{doc}", source_uri=c.path, instruction=para.INSTRUCTION, input=text,
                       output="" if isinstance(out, Exception) else out, metadata={"case_id": c.case_id, "doc_id": doc})
        if isinstance(out, Exception) or not out:
            rejected.append(_reject(s, f"generation_failed:{type(out).__name__ if out else 'empty'}", "TeacherParaphrase"))
            continue
        raw.setdefault(c.case_id, {})[doc] = out
        lost = para.missing_facts(text, out, extraction[c.case_id].get(doc))
        if lost:
            rejected.append(_reject(s, f"fact_missing:{len(lost)}", "FactSurvivalCheck"))
        else:
            samples.append(s)
    # CuratorKIT 0.1.22 HallucinationGate.run([]) raises (range step 0), so skip an empty batch
    passed, gate_rej = (HallucinationGate(judge, threshold=GROUNDING_THRESHOLD, concurrency=workers).run(samples)
                        if samples else ([], []))
    rejected += gate_rej
    gated: dict[str, dict] = {}
    for s in passed:
        gated.setdefault(s.metadata["case_id"], {})[s.metadata["doc_id"]] = s.output
    counts = {"blocks": len(jobs), "rewritten": sum(map(len, raw.values())), "kept": len(passed),
              "rejected": dict(Counter(r.rejection_reason.split(":")[0] for r in rejected))}
    return raw, gated, rejected, counts


def gate_cases(cands: list[Candidate]) -> tuple[list[Candidate], list[RejectedSample], dict]:
    """Case-level curated gates on train candidates (rewrites already applied)."""
    masked = {c.case_id: mask_lost_hsn(c) for c in cands}
    by_id = {c.case_id: masked[c.case_id] or c for c in cands}
    samples = [DataSample(id=c.case_id, source_uri=c.path, instruction=c.prompt, output=c.target,
                          metadata={"split": c.split, "difficulty": c.difficulty}) for c in cands]
    rejected, stage = [], {}

    def step(name: str, keep: list[DataSample], before: list[DataSample], reason: str) -> list[DataSample]:
        ids = {s.id for s in keep}
        rejected.extend(_reject(s, reason, name) for s in before if s.id not in ids)
        stage[name] = {"input_count": len(before), "output_count": len(keep), "rejected_count": len(before) - len(keep)}
        return keep

    s0 = samples
    s1 = step("OcrRecoverability", [s for s in s0 if masked[s.id]], s0, "ocr_unrecoverable")
    stage["OcrRecoverability"]["hsn_masked"] = sum(bool(c.unrecoverable and masked[c.case_id]) for c in cands)
    s2 = step("ExactDeduplicator", ExactDeduplicator().run(s1), s1, "duplicate_exact")
    s3 = step("MinHashDeduplicator", _minhash(s2), s2, "duplicate_near")
    s4, sec_rej = SecretsGate(plugins=SECRET_PLUGINS).run(s3)
    rejected.extend(sec_rej)
    stage["SecretsGate"] = {"input_count": len(s3), "output_count": len(s4), "rejected_count": len(sec_rej)}
    return [by_id[s.id] for s in s4], rejected, {"stage_counts": stage, "passed_samples": s4}


def write_manifest(out: Path, passed: list[DataSample], rejected: list[RejectedSample], stage_counts: dict,
                   t0: float, extra: dict) -> Path:
    result = PipelineResult(passed=passed, rejected=rejected, stage_counts=stage_counts,
                            wall_clock_seconds=time.time() - t0)
    m = ProvenanceManifest(result, output_dir=out, provenance=extra)
    m.write_rejected_sidecar()
    return m.write()
