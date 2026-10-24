"""Smoke + throughput test for the teacher endpoint. Usage: python smoke_teacher.py [base_url] [n_concurrent]"""
import json, sys, time
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI

base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:30000/v1"
n = int(sys.argv[2]) if len(sys.argv) > 2 else 64
c = OpenAI(base_url=base, api_key="none")

r = c.chat.completions.create(model="teacher", messages=[{"role": "user", "content": "Say hi in 5 words."}], max_tokens=32)
print("chat:", r.choices[0].message.content)

schema = {"type": "object", "properties": {"gstin": {"type": "string", "pattern": "^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"},
          "taxable_value": {"type": "number"}, "rate": {"enum": [0, 5, 12, 18, 28]}}, "required": ["gstin", "taxable_value", "rate"], "additionalProperties": False}
r = c.chat.completions.create(model="teacher", max_tokens=200, messages=[{"role": "user", "content": "Invent a GST invoice line as JSON."}],
    response_format={"type": "json_schema", "json_schema": {"name": "line", "schema": schema, "strict": True}})
obj = json.loads(r.choices[0].message.content)
import jsonschema
jsonschema.validate(obj, schema)
print("json_schema ok:", obj)

def one(i):
    r = c.chat.completions.create(model="teacher", max_tokens=256, temperature=0.8,
        messages=[{"role": "user", "content": f"Write a short paragraph (about 200 words) about GST input tax credit, variant {i}."}])
    return r.usage.completion_tokens
t = time.time()
with ThreadPoolExecutor(n) as ex:
    toks = sum(ex.map(one, range(n)))
dt = time.time() - t
print(f"throughput: {n} concurrent reqs, {toks} completion tokens in {dt:.1f}s = {toks/dt:.0f} tok/s")
