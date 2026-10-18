#!/usr/bin/env python
"""Vision locale via Ollama (qwen2.5vl:7b) — contourne vision_analyze (HS ici).
Usage: python vision_ollama.py <image> ["prompt"]"""
import sys, json, base64, urllib.request

MODEL = "qwen2.5vl:7b"
img = sys.argv[1]
prompt = sys.argv[2] if len(sys.argv) > 2 else "Describe this image in detail."
with open(img, "rb") as f:
    b64 = base64.b64encode(f.read()).decode()
body = json.dumps({"model": MODEL, "prompt": prompt, "images": [b64], "stream": False}).encode()
req = urllib.request.Request("http://localhost:11434/api/generate", data=body,
                             headers={"Content-Type": "application/json"})
print(json.loads(urllib.request.urlopen(req, timeout=240).read())["response"])
