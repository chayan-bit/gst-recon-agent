#!/usr/bin/env bash
# Rebuild reports/results.md and reports/results.png from the saved eval runs.
# The tables come from the run directories; reports/results-notes.md is appended as the Notes section,
# and the report command itself appends reports/hybrid.md, reports/pipeline.md and reports/frontier-hybrid.md.
# Usage: RUNS=<dir holding eval/ and the baselines json> scripts/build_results.sh
# Expects RUNS/eval/<run>/aggregate.json for each run below and RUNS/baselines.json from
# `python -m realworld.baselines --n-train 2000 --json RUNS/baselines.json`.
set -euo pipefail
RUNS=${RUNS:?set RUNS to the directory that holds eval/ and baselines.json}
E=$RUNS/eval
python -m gst_recon.eval report \
  --runs "$E"/baseline-keyword "$E"/baseline-context-blind "$E"/teacher-constrained "$E"/teacher-unconstrained \
         "$E"/teacher-constrained-subset "$E"/student-base-constrained-valid "$E"/student-sft-constrained \
         "$E"/student-sft-compact "$E"/student-sft-compact-same36 "$E"/student-sft-unconstrained "$E"/frontier \
  --baselines "$RUNS/baselines.json" --ref "SFT constrained (compact grammar)" \
  --order "keyword (oracle extraction and links)" "context-blind rules (oracle extraction and links)" \
          "teacher-30B constrained" "teacher-30B unconstrained" \
          "teacher-30B constrained (same 19 cases as unconstrained)" \
          "student-base constrained (36 completed cases, 6 realworld lost to host failure)" \
          "SFT constrained (full grammar)" "SFT constrained (compact grammar)" \
          "SFT constrained, compact grammar (same 36 cases)" "SFT unconstrained" "Claude Sonnet (via Claude Code CLI)" \
  --append reports/results-notes.md --out reports/results.md
