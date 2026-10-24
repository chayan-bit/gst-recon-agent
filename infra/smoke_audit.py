# Run in venv-audit against the SGLang teacher through the api: backend. 5 samples, exact-match style scoring.
import sys
import auditkit as ak
from auditkit.model.api_gen import APIModel

base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:30000/v1"
qa = [("What is 12% GST on 1000 rupees? Answer with the number only.", "120"),
      ("Which return summarises monthly GST liability: GSTR-1 or GSTR-3B? Answer with the code only.", "GSTR-3B"),
      ("For interstate supply which tax applies: IGST or CGST? Answer with the code only.", "IGST"),
      ("How many digits are in a GSTIN? Answer with the number only.", "15"),
      ("Is ITC allowed on blocked credits under section 17(5)? Answer yes or no.", "no")]
samples = [ak.Sample(input=q, target=a) for q, a in qa]
model = APIModel(model="teacher", api_base=base, api_key="none")
res = ak.evaluate(samples, model, ["exact_match", "f1_score"])
print(res.summary() if hasattr(res, "summary") else res)
