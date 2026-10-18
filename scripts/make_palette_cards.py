"""
make_palette_cards.py — genere, pour chaque figurine, une carte = photo + bande
de nuanciers (hex EXACTS, ecrits octet par octet sans gestion de couleur), puis
composite via ffmpeg. Palettes inspirees de vraies grenouilles dendrobates.
"""
import os, struct, zlib, subprocess

IMG = "/Users/macia/.hermes/cache/images"
OUT = "/Users/macia/figurine_paint/output/palettes_cards"
FFMPEG = "/Users/macia/figurine_paint/bin/ffmpeg"
os.makedirs(OUT, exist_ok=True)

# (fichier, nom, espece, [(label, hex), ...])
CARDS = [
    ("img_66ea596ed4f1.jpeg", "01_gobelin_chaine", "Oophaga pumilio 'Blue Jeans'", [
        ("corps/tete", "#E0241B"),
        ("jambes/bras", "#2246C9"),
        ("mouchetures/ombres", "#0B0B0B"),
        ("chaine+crochet", "#3A3F44"),
        ("socle", "#2A2320"),
        ("yeux", "#F2EAD3"),
    ]),
    ("img_6748271b65ff.jpeg", "02_crapaud_collerette", "D. tinctorius 'Azureus'", [
        ("peau/corps", "#1E8FE1"),
        ("collerette/membres", "#0B2E73"),
        ("verrues/mouchet.", "#06101F"),
        ("gorge (highlight)", "#7FC4F2"),
        ("lame (os)", "#D9C9A3"),
        ("yeux (or)", "#FFD23F"),
    ]),
    ("img_9798cc9e239a.jpeg", "03_decor_grotte", "Roche + pops leucomelas", [
        ("roche", "#3A3A3F"),
        ("interieur grotte", "#0C0C0F"),
        ("coquillages/corail", "#F2B705"),
        ("trident (bronze)", "#6E5A2E"),
        ("corne/os", "#D9C9A3"),
        ("accents rouges", "#E0241B"),
    ]),
    ("img_674b0a199da7.jpeg", "04_demon_plaques", "D. leucomelas (bumblebee)", [
        ("peau/corps", "#F4B301"),
        ("bandes/oreilles", "#0D0D0D"),
        ("plaques (taches)", "#F4B301"),
        ("lames/armes", "#43494F"),
        ("socle", "#26211C"),
        ("yeux (rouge)", "#E23B2A"),
    ]),
    ("img_4d3e8cdda03c.jpeg", "05_gobelin_souriant", "D. auratus (vert & noir)", [
        ("peau/corps", "#1FA97A"),
        ("marbrures/crete", "#0C0C0C"),
        ("armure segmentee", "#141414"),
        ("dents", "#EDE6CF"),
        ("yeux (or)", "#F2C94C"),
        ("citrouille/socle", "#D2691E"),
    ]),
]

def hex_rgb(h):
    h = h.lstrip("#")
    return bytes(int(h[i:i+2], 16) for i in (0, 2, 4))

def write_swatch(path, colors, W=360, H=1080):
    n = len(colors)
    band = H // n
    rows = []
    for y in range(H):
        bi = min(y // band, n - 1)
        rgb = hex_rgb(colors[bi][1])
        rows.append(b"\x00" + rgb * W)
    raw = b"".join(rows)
    def chunk(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    open(path, "wb").write(png)

made = []
for fname, slug, species, colors in CARDS:
    photo = os.path.join(IMG, fname)
    if not os.path.exists(photo):
        print("MANQUE:", photo); continue
    sw = os.path.join(OUT, f"{slug}_swatch.png")
    write_swatch(sw, colors)
    card = os.path.join(OUT, f"{slug}_card.png")
    cmd = [FFMPEG, "-y", "-i", photo, "-i", sw, "-filter_complex",
           "[0:v]scale=1080:1080[a];[a][1:v]hstack=inputs=2[v]",
           "-map", "[v]", card]
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = r.returncode == 0 and os.path.exists(card)
    print(("OK  " if ok else "FAIL") + f" {slug}  ({species})")
    if not ok:
        print(r.stderr[-600:])
    else:
        made.append(card)

print("\nCARTES:", len(made))
for m in made:
    print(" ", m)
