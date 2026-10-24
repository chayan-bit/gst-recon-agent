# CuratorKIT gate outcomes

Aggregate counts from the manifest of the curation build that the training data came from (stage counts only; no documents, text or paths are published).
Run timestamp 2026-10-24T07:09:56Z, curatorkit 0.1.22, wall clock 643.6 s.
The manifest is `data/train/curated/manifest.json` in the training workspace; data and manifests are not committed to this repository.

## TeacherParaphrase

The teacher (Qwen3-30B-A3B) paraphrases the text-delivered documents; a paraphrase is kept only if every fact string survives a code check and the hallucination gate judges it grounded.

| blocks | rewritten | kept | rejected: fact string missing | rejected: hallucination gate failed |
|---|---|---|---|---|
| 1,242 | 1,242 | 651 (52.4%) | 471 | 120 |

The percentage is 651 divided by 1,242.
An earlier first paraphrase build kept 55% (121 failed the fact check, 28 the hallucination gate); it is superseded by the build above.

## Later stages of the same build

| stage | input | output | rejected | note |
|---|---|---|---|---|
| OcrRecoverability | 1,410 | 1,122 | 288 | 449 HSN values masked |
| ExactDeduplicator | 1,122 | 1,122 | 0 | |
| MinHashDeduplicator | 1,122 | 1,122 | 0 | |
| SecretsGate | 1,122 | 1,122 | 0 | |
