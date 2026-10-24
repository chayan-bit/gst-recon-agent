# Run in venv-curator against the SGLang teacher. ~5 grounded QA samples from 5 short GST texts.
import json, pathlib, sys
from curatorkit import Curator, CuratorConfig

base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:30000/v1"
out = pathlib.Path("smoke/curator"); out.mkdir(parents=True, exist_ok=True)
texts = [
 "Input tax credit (ITC) under GST allows a registered person to reduce tax paid on inputs from the tax payable on outputs, provided the supplier has filed GSTR-1 and the invoice appears in GSTR-2B.",
 "GSTR-3B is a monthly summary return in which a taxpayer declares outward supplies, ITC claimed and the net tax liability, due on the 20th of the following month.",
 "The reverse charge mechanism makes the recipient of goods or services liable to pay GST instead of the supplier, for notified categories such as legal services from advocates.",
 "A tax invoice must carry the GSTIN of the supplier, invoice number, date, HSN code, taxable value, tax rate and amount of CGST, SGST or IGST charged.",
 "Interstate supplies attract IGST, while intrastate supplies attract CGST and SGST in equal parts; the place of supply rules decide which applies.",
]
src = out / "src.jsonl"
src.write_text("\n".join(json.dumps({"text": t}) for t in texts))
cfg = CuratorConfig(dataset=str(src), llm_model="openai/teacher", llm_api_base=base, llm_api_key="none",
                    generation_task="qa", num_questions=1, hallucination_threshold=0.5, reward_threshold=0.5,
                    export_formats=["alpaca"], output_dir=str(out / "run"), llm_concurrency=8)
res = Curator(cfg).run()
res.print_summary()
