"""One ~40k-token prompt with a needle in the middle. Usage: python smoke_longctx.py [base_url] [target_tokens]"""
import sys, time
from openai import OpenAI
from transformers import AutoTokenizer

base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:30000/v1"
target = int(sys.argv[2]) if len(sys.argv) > 2 else 40000
tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-30B-A3B-Instruct-2507-FP8")
para = "Invoice {i}: supplier GSTIN 29ABCDE{i:04d}F1Z5 sold goods worth {v} rupees at 18 percent GST to a registered buyer in Karnataka. "
parts, n, i = [], 0, 0
while n < target:
    s = para.format(i=i, v=1000 + 7 * i)
    if i == 0:
        s += "SECRET-CODE-FOR-AUDIT is PINEAPPLE-4417. "
    parts.append(s); n += len(tok(s).input_ids); i += 1
    if i == 1:
        pass
text = "".join(parts)
mid = len(parts) // 2
text = "".join(parts[:mid]) + "NOTE: the audit passphrase is MANGO-9023. " + "".join(parts[mid:])
prompt = text + "\n\nQuestion: what is the audit passphrase stated in the NOTE? Answer with the passphrase only."
ntok = len(tok(prompt).input_ids)
c = OpenAI(base_url=base, api_key="none", timeout=600)
t = time.time()
r = c.chat.completions.create(model="teacher", messages=[{"role": "user", "content": prompt}], max_tokens=32, temperature=0)
print(f"prompt_tokens={r.usage.prompt_tokens} (counted {ntok}) answer={r.choices[0].message.content!r} wall={time.time()-t:.1f}s")
