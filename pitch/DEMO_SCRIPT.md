# Demo video script (target 2:45, hard limit 3:00)

Visual first: every shot has a picture doing the work, and the narration only names what the viewer is looking at.
Voice-over only, no face cam, 1080p, terminal font at least 18 pt, dark theme.
Numbers in `{{...}}` are read out loud only after they are filled from `NUMBERS.md`; do not record the final voice-over before then.

## Honesty rules for the recording

- Every output on screen comes from a real run of the real pipeline; nothing is mocked, edited or typed in by hand.
- Any sped-up or cut segment carries an on-screen label ("8x speed", "cut: 90 s of generation").
- The demo company, GSTINs and invoices are synthetic, and a small caption says so on the first shot that shows them.
- No hostnames, usernames, private paths or tokens on screen: serve through `localhost:30000` and hide the shell prompt.
- If a shot cannot be produced from a real run before the deadline, cut the shot, not the honesty.

## Assets to prepare (none of these exist in the repo yet unless marked committed)

| Asset | Status | Notes |
|---|---|---|
| Scanned invoice image | committed: `examples/test_iid-hard-23-00001/images/D05.png` (also `D17.png`) | Skewed, stamped, photocopy-degraded; use for shot 2 |
| WhatsApp-style text bill | committed: D01 in `examples/test_iid-hard-23-00001/prompt.txt` | The tea-and-sugar bill used in shot 4 |
| Demo case run through the trained student | to do | Pick one medium case from `test_iid` that has a blocked, context-dependent invoice the student gets right; if it differs from the committed example, replace the rupee figures below with the ones on screen |
| Streaming client | to do | A small script that posts the prompt with `stream: true` and `response_format` json_schema and prints tokens plus the tokens/s from the server; keep it under 50 lines, not part of the evaluation code |
| Reconciliation table view | to do | Render the model's JSON as a table (terminal `rich` or a static HTML page); columns: document, supplier, taxable, matched, flags, ITC eligible, blocked, deferred, reason |
| Results charts | to do | From `python -m gst_recon.eval report` after the final runs; `reports/smoke/results.png` is only a layout reference, not results |
| Contribution cards | to do | Four static slides, one per toolkit, each with the repo link and one before/after line |

## Shots

### Shot 1 - The problem (0:00 to 0:14)

On screen: a stack of paper invoices crossing out to a cloud icon with a red cross, then a padlocked "your network" box with a GPU in it.
Caption: "Synthetic data shown."

Narration:
"Every month, a company works out how much GST it can claim back on what it bought.
The inputs are its invoices, its bank statement and its supplier list.
That is exactly the data you do not want to paste into a cloud API."

### Shot 2 - Messy documents in (0:14 to 0:34)

On screen: the scan `D05.png` full frame, slow zoom on the skew and the stamp, then a cut to the WhatsApp bill, then a terminal pane where Tesseract output fills in as text next to the image.
Then a terminal showing `curl localhost:30000/v1/models` returning the served model name, and a one-line GPU memory readout (`nvidia-smi` memory used only).

Narration:
"One month looks like this: scans, photos, a WhatsApp message.
Tesseract turns the scans into text, on the same machine.
Our model reads that text, so a bad scan can lose a field, and we measure how often that happens.
From here on, everything runs on one GPU, behind the firewall."

### Shot 3 - Constrained JSON streaming out (0:34 to 1:02)

On screen: split terminal.
Left: the request, with the `response_format` block that carries the JSON schema highlighted.
Right: JSON streaming token by token, with a live tokens-per-second counter, labelled "8x speed" if sped up.
Overlay callouts appear as the stream passes them: a GSTIN (pattern matched), then a `flags` array, then an `itc` row with `eligible`, `blocked`, `deferred`.

Narration:
"The model is a 4 billion parameter open model, served on SGLang.
The output schema is compiled into a grammar by XGrammar, so it can only produce valid JSON: every key is there, every GSTIN has the right shape.
Per invoice it extracts the fields, matches it to the books, the government's 2B statement and the bank, and then decides how much tax credit is allowed."

### Shot 4 - The reconciliation table and one blocked credit (1:02 to 1:34)

On screen: the reconciliation table fills in, rows green except one.
Zoom on the red row: supplier "Shree Global", lines "Taj Mahal tea" and "Uttam sugar", remark "annual day celebration", buyer "construction contractor", blocked amount Rs 5,713.44, reason `BLOCKED_FOOD_BEVERAGE`, "Sec 17(5)(b)(i)".
Side panel: the same row from the simulator's ground truth, with a green check because the amounts match to the rupee (show this only if they do, otherwise show the real difference).
Optional second beat, only if a real re-run supports it: the same invoice with the buyer changed to a caterer, now green and eligible.
If that re-run is not available, show the one-line rule card instead: "Food and beverages: blocked, unless the buyer is a hotel or caterer".
A last quick highlight on a yellow row: "deferred: unpaid for more than 180 days".

Narration:
"Here is the part an accountant cares about.
This invoice is tea and sugar, for an annual day celebration, bought by a construction contractor.
The model blocks five thousand seven hundred and thirteen rupees of credit, and cites section 17(5)(b)(i).
A caterer buying the same sugar could claim it, so the model has to read the buyer, not just the item."

### Shot 5 - The results chart (1:34 to 2:03)

On screen: the staircase chart, one step revealed at a time: base, SFT, SFT plus GRPO, each with ITC-exact on unseen items and layouts and a bootstrap interval.
Then Claude Sonnet and the 30B teacher appear as two extra markers.
Then a small bar pair: constrained versus unconstrained decoding.
A footer on the chart reads "held-out out-of-distribution cases, n = 60".

Narration:
"We do not claim to beat frontier models.
We measured the climb.
On unseen items and layouts, invoices exactly right go from {{BASE_ITCEXACT_OOD}} percent for the base model, to 13.7 with SFT, to {{GRPO_ITCEXACT_OOD}} with GRPO on a rule-checked reward.
Claude Sonnet gets 97.8: the local model reaches {{Y_PCT_OF_SONNET_ACCURACY}} percent of that, at {{Z_COST_PCT}} percent of the cost.
Constrained decoding lifts valid output from {{GRPO_SCHEMA_VALID_UNCON}} to {{GRPO_SCHEMA_VALID_CON}} percent."

<!-- Sources: n = 60 and Sonnet 97.8 are reports/results.md, test_ood rows. SFT 13.7 is the "SFT constrained (full grammar)" test_ood row, a format mismatch: replace it with the compact-grammar run before recording the voice-over. -->

### Shot 6 - What we built for the sponsor stack (2:03 to 2:33)

On screen: four cards, about six seconds each, each with a repo link and one before/after line.
1. AlignTune: "SGLang rollout backend for GRPO" with the measured rollout speedup {{ROLLOUT_SPEEDUP_X}}x and the line "prefill shared across samples: 1216 of 1216 prompt tokens cached".
2. AuditKIT: "structured-extraction metrics" and the p-value fix, with a mini before/after "p = 0.52 before the fix on 50 pairs with means 0.11 versus 0.80; after it, a regression test of a comparable large effect asserts p below 0.01".
3. AlignTune bugs: "the dataset fingerprint pickled the whole trainer: 42.7 GB of host RAM", plus "YAML values silently overridden" and "train keys silently dropped".
4. CuratorKIT: "651 of 1,242 teacher paraphrases kept; 471 failed the fact check, 120 failed the hallucination gate".

Narration:
"We also built back into the sponsors' tools.
AlignTune gets an SGLang rollout backend for GRPO: each prompt is prefilled once and shared across samples.
AuditKIT gets structured-extraction metrics, and a fix for significance tests that always came out near fifty-fifty.
We documented three AlignTune bugs, one of which ate forty-two gigabytes of host RAM.
And CuratorKIT's gates caught the teacher's hallucinations: only 651 of 1,242 paraphrases survived."

### Shot 7 - Honest close (2:33 to 2:47)

On screen: a plain card with three lines and the repo QR code.
Lines: "Trained and tested on a simulator"; "Real-world sanity set: 36 public-format documents, field F1 {{REAL_FIELD_F1}}"; "Code, generator and evals are open".

Narration:
"This is trained and tested on a simulator, so we also check a small set of real sample formats, and we report what breaks.
Private financial reasoning, on one GPU.
Code and evals are in the repo."

## Timing and length check

Narration is about 410 words (count it again once the placeholders are filled), which is about 2:45 at 150 words per minute.
If the final cut runs over 3:00, remove the optional second beat in shot 4 first, then the AlignTune bugs card in shot 6.
Do not remove shot 5's constrained-versus-unconstrained pair or shot 7's limitation line.

## Fallbacks if something is not ready by the deadline

- No GRPO model yet: shot 5 shows base and SFT only, and the narration says "GRPO is still training"; do not show a GRPO bar.
- No real-world set yet: shot 7 drops the second line and says "a real-document check is the next step".
- Rollout speedup not measured: shot 6 card 1 shows only the measured cache-sharing line, not a speedup.
- Student cannot stream a full case in time: show the first 20 seconds of the stream and the final table, with the "cut" label.
