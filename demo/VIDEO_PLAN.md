# Submission video plan (3:00 hard limit, target 2:55)

The shot list we used for the three-minute demo video: what is on screen, what to say, and which real run backs each shot.
Pipeline names: end-to-end means one model call for the whole case; hybrid means the model reads one document at a time and code does the matching and tax rules; pd3g287 is the shipped per-document adapter (see the top-level README).

This plan uses only recorded runs, replayed through the demo app, so the video needs no GPU and cannot stall.
Every run on screen is a real run saved in `recordings/`; the app labels it "REPLAY · RECORDED · 8x" in the middle panel, and that badge must stay visible in every replay shot.
Voice-over is the author's own voice, no face cam: each `VO` block below is a prompt for what to say, not a script to read word for word.
Numbers in the prompts come from the screen or from `reports/`; say them only as they appear.
The sponsor-tool material from `pitch/DEMO_SCRIPT.md` shot 6 is covered by the single static slide in shot 6 below; the QR close from its shot 7 is not in this plan.

## Setup before recording

```bash
cd demo && uv run uvicorn gst_demo.app:app --port 8765    # no tunnel needed, replay only
```

- Open `http://localhost:8765/` at 1920x1080, browser zoom 100%, dark theme, bookmarks bar and tabs hidden, nothing else in the frame.
- Source = Replay, Speed = 8x, "Compare with ground truth" on.
- With no tunnel the status pill reads "Offline · 12 recorded runs"; that is accurate for a replay, leave it.
- No hostnames, usernames or paths appear in the app; do not open a terminal in frame.
- Dry-run each shot once, then record each as its own clip so a slip costs one clip, not the take.

## Shot list

### Shot 1 - The problem and the promise (0:00 to 0:15)

Screen: the idle app on the hard case (`test_iid-hard-23-00001`), left panel showing the scan `D05`, footer visible: "Running locally on one GPU via SGLang · data never leaves the machine".
Caption on screen: "Synthetic data" (the footer already says the company and invoices are synthetic).

VO prompt: every month a company works out how much GST credit it can claim; the inputs are invoices, bank statement and supplier list; that is data you do not want in a cloud API, so this runs on one GPU on the machine.

### Shot 2 - Messy documents in (0:15 to 0:23)

Screen: left panel only.
Click D05 (the skewed, stamped scan), pause 2 s, click `Document text (OCR)`, then click the Purchase register tab for 1 s.
D01 shows "No scan for this document: it arrived as email or WhatsApp text"; click D01 and show its OCR text ("good morning sir. bill attached", Taj Mahal tea, Uttam sugar, "annual day celebration").

VO prompt: scans, photos and a WhatsApp message; Tesseract turns them into text; the model reads that text, so a bad scan can lose a field.

### Shot 3 - Per-document hybrid on the hard case (0:23 to 0:58)

Screen: Pipeline = Hybrid, Model = Per-document SFT + GRPO (shipped), press Run (R).
The 23 document chips tick off one by one (recorded run is 247 s; at 8x it takes about 31 s), then the line "Then: code reconciler, no model" appears (about 0.25 s), then the table fills.
Hold 3 s on the finished screen: headline cards and "ITC exact 17/23" with ground truth on.
Overlay text for this shot: "REPLAY, 8x speed. Recorded run: 247 s, 6,104 tokens, 23 documents."

VO prompt: a 4B model reads one document at a time, constrained to a JSON schema so it can only produce valid output; then ordinary code does the matching to the books, GSTR-2B and bank, and applies the tax rules; 17 of 23 invoices are exactly right on the hard case, and the headline totals are still off from the truth (eligible and deferred), which the comparison view shows rather than hides.

### Shot 4 - Tea and sugar, blocked, with the reason (0:58 to 1:28)

Screen: scroll the table to the top (it opens the first two blocked or deferred rows automatically).
Row D01, Shree Global: "Blocked: food and beverages, Sec 17(5)(b)(i)", blocked ₹5,713.44, "MATCHES TRUTH".
Slowly pan the open trace: "Taj Mahal tea was read as food and beverages, for staff welfare: blocked", "Uttam sugar (Lot 2)" the same, GSTR-2B entry matched, purchase register voucher matched, "invoice is 215 days old at the return date, fully paid; paid, so the 180-day reversal rule does not apply".
Flip to the left panel and show the D01 OCR text with the remark "annual day celebration" for 3 s, then back to the table.

VO prompt: this is tea and sugar for an annual day celebration; the model reads the line items and the purpose; the code blocks ₹5,713.44 and cites section 17(5)(b)(i); the trace says why in plain words, so an accountant can check it.

Do not show the "caterer buys the same sugar" re-run: the app has no recording for it.
If the point is wanted, say it in words only: a caterer buying the same sugar could claim it, so the buyer matters.

### Shot 5 - End-to-end versus hybrid: the 180-day rule (1:28 to 2:00)

Part A, end-to-end (about 16 s).
Switch Pipeline to End-to-end, Model to Fine-tuned (SFT), Run.
The JSON streams token by token in the middle panel (recorded run: 142 s, 8,044 tokens, 57 tok/s; at 8x about 18 s, so cut to the last 8 s of the stream with a "cut: 10 s of generation" label).
Overlay text: "REPLAY, 8x speed. One call, whole case, model only."
When it finishes, point at the headline: deferred ₹0.00 against truth ₹5,07,180.51, "ITC exact 15/23".
Open D02, Chawla Networks (₹17,00,498.75): the model puts ₹2,59,398.12 under ITC eligible, while the truth is deferred ("Unpaid over 180 days, Sec 16(2), Rule 37").

Part B, hybrid (about 16 s).
Switch back to Hybrid, Per-document SFT + GRPO (shipped), replay; jump to the finished table (re-run at 8x or cut to a saved clip).
Open D02 and show the trace: "Payment: invoice is N days old at the return date, ₹17,00,498.75 of ₹17,00,498.75 unpaid; unpaid for over 180 days, credit must be reversed" (read N off the screen), deferred ₹2,59,398.18, "MATCHES TRUTH".
The date arithmetic is code, not a model guess.

VO prompt: on the same case, the end-to-end model never defers an invoice that is unpaid for more than 180 days, so it claims credit the law says must be reversed; in hybrid the model only reads, and the code counts the days against the bank statement.

Honest framing, say it or caption it: these are two different models (the whole-case SFT adapter versus the per-document adapter), so this contrast compares two pipelines, not one model in two modes.
Do not use the medium case for this contrast: there the end-to-end SFT run (9/13 exact) beats the SFT hybrid run (3/13 exact).

### Shot 6 - How it is built (2:00 to 2:20)

Screen: the static slide `http://localhost:8765/built` (screenshot: `screenshots/21-built.png`), no recording needed.
Six tiles, in this order, about 3 s each: SGLang multi-LoRA serving (base, base:sft, base:perdoc on one server); XGrammar constrained decoding (schema as `response_format`); RadixAttention shared prefill (1216 of 1216 prompt tokens cached, against 0 as separate requests); the AlignTune SGLang rollout backend for GRPO; CuratorKIT gates (651 of 1,242 teacher paraphrases kept: 471 failed the fact check, 120 the hallucination gate); AuditKIT structured-extraction metrics.
End on the badge for 3 s: "11 pull requests open upstream, none merged" (AlignTune 4, CuratorKIT 3, AuditKIT 3, SGLang 1).

VO prompt: one SGLang server serves the base model and two LoRA adapters, switched per request; XGrammar makes the JSON always valid; RadixAttention shares the prompt prefill, which is what made GRPO rollouts cheap enough, and we built that as the AlignTune SGLang backend; CuratorKIT filtered the teacher's data and AuditKIT scored the extraction; eleven pull requests are open upstream and none is merged yet, and we say so.
Say "open, none merged" exactly; do not say "merged" or "accepted".

### Shot 7 - The real-document results (2:20 to 2:50)

Screen: open `http://localhost:8765/results` (the footer link "Results chart"); the bars animate in.
Page content (from the README Results table, 54 real supplier documents with simulated books; no simulated-test numbers are shown): ITC exact / match / composite / invented IDs for Claude Haiku 5.5 (84.9 / 88.4 / 86.5 / 8.4%), GPT-6 luna reasoning off (70.6 / 82.5 / 77.9 / 15.4%), Claude Haiku 4.5 thinking off (68.2 / 82.2 / 77.4 / 16.6%) and ours, pd3g287 (61.1 / 71.5 / 72.9 / 9.7%).

VO prompt: on 54 real supplier documents the frontier readers lead, and we say so; ours is a 4B model on one 16 GB GPU with nothing leaving the machine, and it invents fewer identity fields than Haiku 4.5 and luna; most of its loss is misreading amounts off the page, and the labels were drafted by a model, not verified by a human.

### Shot 8 - Honest close (2:50 to 3:00)

Screen: back to the live app footer, or a plain card: "Trained and tested on a simulator", "Code and evals are open".

VO prompt: this is trained and tested on a simulator, so the limits are real; private financial reasoning on one GPU; code and evals are in the repo.

## Honesty checklist

- Every table, stream and trace is a replay of a real recorded run; the replay badge is visible in shots 3 and 5; the "how it is built" slide in shot 6 is a static slide, not a run, and says so in its source line.
- Sped-up segments carry the "8x" label.
- The shipped-model (GRPO) hard-case hybrid run is 17/23 exact (the earlier SFT-only run was 19/23; do not mix them), not perfect; the headline totals differ from truth and the video says so.
- The reconciler version is in the footer in hybrid mode (for example `reconciler 4f60882`; it is the latest reconciler commit at start-up, so say the hash on screen), and "end-to-end (model only)" in end-to-end mode.
- The "caterer buys the same sugar" re-run is not supported by the app and is not shown.

## Timing summary

| Shot | Start | Length |
|---|---|---|
| 1 Problem | 0:00 | 15 s |
| 2 Messy documents | 0:15 | 8 s |
| 3 Per-document hybrid, hard case | 0:23 | 35 s |
| 4 Tea and sugar blocked, trace | 0:58 | 30 s |
| 5 End-to-end versus hybrid | 1:28 | 32 s |
| 6 How it is built (static slide) | 2:00 | 20 s |
| 7 Results chart | 2:20 | 30 s |
| 8 Close | 2:50 | 10 s |

If it runs over 3:00, cut in this order: shot 2's register tab, then the JSON stream in shot 5 part A (keep only the table), then the overclaim panel in shot 7.
