# Submission video plan (3:00 hard limit, target 2:55)

This plan uses only recorded runs, replayed through the demo app, so the video needs no GPU and cannot stall.
Every run on screen is a real run saved in `recordings/`; the app labels it "REPLAY · RECORDED · 8x" in the middle panel, and that badge must stay visible in every replay shot.
Voice-over is the user's own voice, no face cam: each `VO` block below is a prompt for what to say, not a script to read word for word.
Numbers in the prompts come from the screen or from `reports/`; say them only as they appear.
The sponsor-tool cards (AlignTune, AuditKIT, CuratorKIT) and the QR close from `pitch/DEMO_SCRIPT.md` shots 6 and 7 are not in this plan; if they are wanted, cut shot 2 to 10 s and shot 5 to 20 s to make room.

## Setup before recording

```bash
cd demo && uv run uvicorn gst_demo.app:app --port 8765    # no tunnel needed, replay only
```

- Open `http://localhost:8765/` at 1920x1080, browser zoom 100%, dark theme, bookmarks bar and tabs hidden, nothing else in the frame.
- Source = Replay, Speed = 8x, "Compare with ground truth" on.
- With no tunnel the status pill reads "Offline · 10 recorded runs"; that is accurate for a replay, leave it.
- No hostnames, usernames or paths appear in the app; do not open a terminal in frame.
- Dry-run each shot once, then record each as its own clip so a slip costs one clip, not the take.

## Shot list

### Shot 1 - The problem and the promise (0:00 to 0:15)

Screen: the idle app on the hard case (`test_iid-hard-23-00001`), left panel showing the scan `D05`, footer visible: "Running locally on one GPU via SGLang · data never leaves the machine".
Caption on screen: "Synthetic data" (the footer already says the company and invoices are synthetic).

VO prompt: every month a company works out how much GST credit it can claim; the inputs are invoices, bank statement and supplier list; that is data you do not want in a cloud API, so this runs on one GPU on the machine.

### Shot 2 - Messy documents in (0:15 to 0:30)

Screen: left panel only.
Click D05 (the skewed, stamped scan), pause 3 s, click `Document text (OCR)`, then click the Purchase register, GSTR-2B and Bank statement tabs, 2 s each.
D01 shows "No scan for this document: it arrived as email or WhatsApp text"; click D01 and show its OCR text ("good morning sir. bill attached", Taj Mahal tea, Uttam sugar, "annual day celebration").

VO prompt: scans, photos and a WhatsApp message; Tesseract turns them into text; the model reads that text, so a bad scan can lose a field.

### Shot 3 - Per-document hybrid on the hard case (0:30 to 1:05)

Screen: Pipeline = Hybrid, Model = Per-document (PERDOC), press Run (R).
The 23 document chips tick off one by one (recorded run is 208 s; at 8x it takes about 30 s), then the line "Then: code reconciler, no model" appears (about 0.25 s), then the table fills.
Hold 3 s on the finished screen: headline cards and "ITC exact 19/23" with ground truth on.
Overlay text for this shot: "REPLAY, 8x speed. Recorded run: 208 s, 6,330 tokens, 23 documents."

VO prompt: a 4B model reads one document at a time, constrained to a JSON schema so it can only produce valid output; then ordinary code does the matching to the books, GSTR-2B and bank, and applies the tax rules; 19 of 23 invoices are exactly right on the hard case, and the headline totals are still off from the truth (eligible and deferred), which the comparison view shows rather than hides.

### Shot 4 - Tea and sugar, blocked, with the reason (1:05 to 1:35)

Screen: scroll the table to the top (it opens the first two blocked or deferred rows automatically).
Row D01, Shree Global: "Blocked: food and beverages, Sec 17(5)(b)(i)", blocked ₹5,713.44, "MATCHES TRUTH".
Slowly pan the open trace: "Taj Mahal tea was read as food and beverages, for staff welfare: blocked", "Uttam sugar (Lot 2)" the same, GSTR-2B entry matched, purchase register voucher matched, "215 days since the invoice, fully paid".
Flip to the left panel and show the D01 OCR text with the remark "annual day celebration" for 3 s, then back to the table.

VO prompt: this is tea and sugar for an annual day celebration; the model reads the line items and the purpose; the code blocks ₹5,713.44 and cites section 17(5)(b)(i); the trace says why in plain words, so an accountant can check it.

Do not show the "caterer buys the same sugar" re-run: the app has no recording for it.
If the point is wanted, say it in words only: a caterer buying the same sugar could claim it, so the buyer matters.

### Shot 5 - End-to-end versus hybrid: the 180-day rule (1:35 to 2:20)

Part A, end-to-end (about 20 s).
Switch Pipeline to End-to-end, Model to Fine-tuned (SFT), Run.
The JSON streams token by token in the middle panel (recorded run: 142 s, 8,044 tokens, 57 tok/s; at 8x about 18 s).
Overlay text: "REPLAY, 8x speed. One call, whole case, model only."
When it finishes, point at the headline: deferred ₹0.00 against truth ₹5,07,180.51, "ITC exact 15/23".
Open D02, Chawla Networks (₹17,00,498.75): the model puts ₹2,59,398.12 under ITC eligible, while the truth is deferred ("Unpaid over 180 days, Sec 16(2), Rule 37").

Part B, hybrid (about 20 s).
Switch back to Hybrid, Per-document (PERDOC), replay; jump to the finished table (re-run at 8x or cut to a saved clip).
Open D02 and show the trace: "Payment: 204 days since the invoice, ₹17,00,498.75 of ₹17,00,498.75 unpaid; unpaid for over 180 days, credit must be reversed", deferred ₹2,59,398.14, "MATCHES TRUTH".
The date arithmetic is code, not a model guess.

VO prompt: on the same case, the end-to-end model never defers an invoice that is unpaid for more than 180 days, so it claims credit the law says must be reversed; in hybrid the model only reads, and the code counts the days against the bank statement.

Honest framing, say it or caption it: these are two different models (the whole-case SFT adapter versus the per-document adapter), so this contrast compares two pipelines, not one model in two modes.
Do not use the medium case for this contrast: there the end-to-end SFT run (9/13 exact) beats the SFT hybrid run (3/13 exact).

### Shot 6 - The results chart (2:20 to 2:50)

Screen: open `http://localhost:8765/results` (the footer link "Results chart"); the bars animate in.
Walk left to right: code alone 10.4, SFT end-to-end 10.9 (format mismatch footnote), base hybrid 55.2, SFT hybrid 46.8, per-doc v1 62.9, v2 73.1, v3 79.9, GRPO as a dashed TODO bar; then teacher 30B 59.8 and Claude Sonnet 96.3 on the right.
Then the side panel: per-document v3 context accuracy 82.7% and overclaim Rs 27,183 per case, against the teacher at 38.8% and Rs 3,83,144.
Footer text on the page: ITC invoice exact, 120 simulator test cases, every number cites its commit.

VO prompt: ITC invoice exact on 120 held-out simulator cases; code alone is 10; the per-document model with better reconciler versions climbs from 63 to 80 on the same model replies; the 30B teacher is 60 and Claude Sonnet is 96, so we are not claiming to beat a frontier model; the local model overclaims far less than the teacher.
If GRPO numbers have landed by recording time, update `static/results.json` first and say the number; otherwise leave the dashed bar and say "GRPO is still training".

### Shot 7 - Honest close (2:50 to 3:00)

Screen: back to the live app footer, or a plain card: "Trained and tested on a simulator", "Code and evals are open".

VO prompt: this is trained and tested on a simulator, so the limits are real; private financial reasoning on one GPU; code and evals are in the repo.

## Honesty checklist

- Every table, stream and trace is a replay of a real recorded run; the replay badge is visible in shots 3 and 5.
- Sped-up segments carry the "8x" label.
- The hard-case hybrid run is 19/23 exact, not perfect; the headline totals differ from truth and the video says so.
- The reconciler version is in the footer in hybrid mode (`reconciler 8286f1f`), and "end-to-end (model only)" in end-to-end mode.
- The SFT end-to-end bar on the chart is a format mismatch (strict grammar), footnoted on the page; the compact-grammar number is the end-to-end SFT run in shot 5.
- The "caterer buys the same sugar" re-run is not supported by the app and is not shown.

## Timing summary

| Shot | Start | Length |
|---|---|---|
| 1 Problem | 0:00 | 15 s |
| 2 Messy documents | 0:15 | 15 s |
| 3 Per-document hybrid, hard case | 0:30 | 35 s |
| 4 Tea and sugar blocked, trace | 1:05 | 30 s |
| 5 End-to-end versus hybrid | 1:35 | 45 s |
| 6 Results chart | 2:20 | 30 s |
| 7 Close | 2:50 | 10 s |

If it runs over 3:00, cut in this order: shot 2's register, 2B and bank tab tour, then the second half of shot 5 part A (the JSON stream), then the overclaim panel in shot 6.
