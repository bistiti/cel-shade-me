import subprocess, json, time, os

OUT = "/Users/macia/figurine_paint/output/palettes_v2"
os.makedirs(OUT, exist_ok=True)
ENV = dict(os.environ, PATH="/Users/macia/.local/bin:" + os.environ.get("PATH", ""))

def hf(*args, timeout=150):
    return subprocess.run(["higgsfield", *args], capture_output=True, text=True, env=ENV, timeout=timeout)

PRE = ("Professional studio macro photograph of a REAL physical hand-painted tabletop miniature figurine "
       "(about 35mm, resin) on a round hobby base. Hand-painted by a master miniature painter using Vallejo "
       "acrylic paints in a crisp CEL-SHADING box-art / 2D comic technique: hard-edged shadow zones, bold sharp "
       "edge highlights, dark liner in the recesses, smooth MATTE acrylic finish with subtle real brush and "
       "airbrush micro-texture. Soft diffused studio softbox lighting, realistic contact shadow under the base, "
       "shallow depth of field with slight background blur, neutral dark grey atmospheric backdrop. Must look like "
       "a REAL painted miniature photographed for a catalog, with physical paint texture, NOT a flat digital "
       "illustration, NOT vector art. Keep the EXACT same pose, sculpt, proportions and composition as the source. ")

P02 = (PRE + "Subject: a fierce frilled toad creature with a wide neck frill. Skin painted deep RED "
       "(base #C13D2E, shadows #781316 and #510A11, highlights #F38D6E) like a strawberry poison dart frog, "
       "the frill/collar a slightly darker red. Scattered black markings (#0D0D0D). Bone and claw details "
       "painted cream. Eyes glowing cyan accent (#38BCCB).")

P05 = (PRE + "Subject: a grinning goblin poison-frog warrior. Skin and body painted vivid FLUORESCENT YELLOW "
       "(base #E0DD12, shadows #8B7600 and #5E4A00, highlights #EBFF56) like a bumblebee poison dart frog, with "
       "bold BLACK markings and marbling (#0C0C0C). Armor painted black. Teeth off-white. Eyes glowing "
       "blue-violet accent (#1E21EB).")

JOBS = [
    ("02_crapaud", "/Users/macia/.hermes/cache/images/img_6748271b65ff.jpeg", P02),
    ("05_gobelin_souriant", "/Users/macia/.hermes/cache/images/img_4d3e8cdda03c.jpeg", P05),
]

def get_status(jid):
    r = hf("generate", "get", jid, "--json")
    try:
        d = json.loads(r.stdout); return d.get("status"), d.get("result_url")
    except Exception:
        return None, None

def wait_dl(jid, name, maxwait=300):
    t0 = time.time()
    while time.time() - t0 < maxwait:
        st, url = get_status(jid)
        if st == "completed" and url:
            subprocess.run(["curl", "-sL", "-o", f"{OUT}/{name}.png", url])
            open(f"{OUT}/{name}.url", "w").write(url)
            return url
        if st in ("failed", "canceled"):
            return None
        time.sleep(10)
    return None

def submit(img, prompt, retries=8):
    for _ in range(retries):
        r = hf("generate", "create", "seedream_v5_lite", "--image", img, "--prompt", prompt, "--aspect-ratio", "3:4", "--json")
        try:
            d = json.loads(r.stdout); jid = d[0] if isinstance(d, list) else d.get("id")
            if jid:
                return jid
        except Exception:
            pass
        time.sleep(10)  # rate_limit: wait for the slot to free
    return None

# 1) finish already-submitted job 01
j01 = open("/Users/macia/.hermes/cache/scratch/jid_01_gobelin_chaine.txt").read().strip()
print("01 waiting", j01, flush=True)
print("01 result:", wait_dl(j01, "01_gobelin_chaine"), flush=True)

# 2) serialize the remaining two
for name, img, prompt in JOBS:
    jid = submit(img, prompt)
    print(name, "submitted", jid, flush=True)
    if not jid:
        print(name, "SUBMIT_FAILED", flush=True); continue
    print(name, "result:", wait_dl(jid, name), flush=True)

print("ALL_DONE", flush=True)
