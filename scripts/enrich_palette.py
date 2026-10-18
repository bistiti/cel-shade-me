#!/usr/bin/env python3
"""
Enrichit data/vallejo_mecha_palette.json avec les NOMS officiels et les
ÉQUIVALENCES (Vallejo Model Color, Mr.Color) lues dans CC337-Mecha_Color_b-1.pdf
(section "Mecha Color equivalences"). Ajoute aussi la catégorie de chaque réf.
"""
import json
import os

PALETTE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "data", "vallejo_mecha_palette.json")

# code -> (nom officiel, equiv Vallejo Model Color, equiv Mr.Color, catégorie)
# Catégories: shade (42), fluo (4), metallic (11), weathering (11),
#             primer (5), auxiliary (7)
DATA = {
    # --- 42 teintes de base ---
    "69.001": ("Pure White", "70.951", "UG01", "shade"),
    "69.002": ("White Grey", "70.313", "C69", "shade"),
    "69.003": ("Off-White", "70.820", "UG03", "shade"),
    "69.004": ("Yellow", "70.953", "-", "shade"),
    "69.005": ("Light Flesh", "70.928", "-", "shade"),
    "69.006": ("Pink", "70.805", "UG10", "shade"),
    "69.007": ("Orange", "70.851", "-", "shade"),
    "69.008": ("Red", "70.817", "UG04", "shade"),
    "69.009": ("SZ Red", "70.947", "UG12", "shade"),
    "69.010": ("Magenta", "70.945", "-", "shade"),
    "69.011": ("Dark Red", "70.926", "UG11", "shade"),
    "69.012": ("Purple", "-", "UG08", "shade"),
    "69.013": ("Titan Blue", "70.807", "UG17", "shade"),
    "69.014": ("Grey Green", "70.904", "C337", "shade"),
    "69.015": ("Blue Grey", "70.901", "C74", "shade"),
    "69.016": ("Light Blue", "70.902", "UG14", "shade"),
    "69.017": ("Sky Blue", "70.961", "C323", "shade"),
    "69.018": ("Deep Blue", "70.841", "C72", "shade"),
    "69.019": ("Blue", "70.962", "UG02", "shade"),
    "69.020": ("Electric Blue", "70.736", "UG13", "shade"),
    "69.021": ("Dark Blue", "70.965", "C322", "shade"),
    "69.022": ("Titan Dark Blue", "70.898", "UG16", "shade"),
    "69.023": ("Turquoise", "70.966", "C72*", "shade"),
    "69.024": ("Stone Grey", "70.973", "C308", "shade"),
    "69.025": ("Light Green", "70.832", "C314", "shade"),
    "69.026": ("Green", "70.885", "UG06", "shade"),
    "69.027": ("Green Blue", "70.974", "CG24", "shade"),
    "69.028": ("Olive Green", "70.967", "C304", "shade"),
    "69.029": ("Deep Green", "70.330", "UG07", "shade"),
    "69.030": ("Dark Green", "70.894", "CG23", "shade"),
    "69.031": ("Grey Sand", "70.821", "-", "shade"),
    "69.032": ("Yellow Ochre", "70.834", "C109", "shade"),
    "69.033": ("Sand Yellow", "70.916", "C39", "shade"),
    "69.034": ("Brown", "70.873", "C310", "shade"),
    "69.035": ("Chipping Brown", "70.822", "-", "shade"),
    "69.036": ("Light Grey", "70.989", "C338*", "shade"),
    "69.037": ("Grey", "71.120", "-", "shade"),
    "69.038": ("Medium Grey", "70.870", "C335", "shade"),
    "69.039": ("Grey Z", "70.991", "UG09", "shade"),
    "69.040": ("Phantom Grey", "70.868", "UG15", "shade"),
    "69.041": ("Dark Grey Green", "70.862", "CG100", "shade"),
    "69.042": ("Pure Black", "70.950", "-", "shade"),
    # --- 4 fluorescentes ---
    "69.054": ("Yellow Fluorescent", "-", "-", "fluo"),
    "69.055": ("Orange Fluorescent", "-", "-", "fluo"),
    "69.056": ("Magenta Fluorescent", "-", "-", "fluo"),
    "69.057": ("Green Fluorescent", "-", "-", "fluo"),
    # --- 11 métalliques ---
    "69.058": ("Gunmetal", "72.054", "UG05", "metallic"),
    "69.059": ("Gold", "70.793", "-", "metallic"),
    "69.060": ("Old Gold", "70.878", "-", "metallic"),
    "69.061": ("Copper", "70.999", "-", "metallic"),
    "69.062": ("Bronze", "70.998", "-", "metallic"),
    "69.063": ("Steel", "70.864", "-", "metallic"),
    "69.064": ("Light Steel", "70.997", "-", "metallic"),
    "69.065": ("Dark Steel", "70.865", "-", "metallic"),
    "69.066": ("Metallic Red", "71.070", "-", "metallic"),
    "69.067": ("Metallic Blue", "71.071", "-", "metallic"),
    "69.068": ("Metallic Green", "-", "-", "metallic"),
    # --- 11 weathering ---
    "69.505": ("Light Rust Wash", "76.505", "-", "weathering"),
    "69.507": ("Dark Rust Wash", "76.507", "-", "weathering"),
    "69.515": ("Light Grey Wash", "76.515", "-", "weathering"),
    "69.518": ("Black Wash", "76.518", "-", "weathering"),
    "69.521": ("Oiled Earth Wash", "76.521", "-", "weathering"),
    "69.522": ("Desert Dust Wash", "76.522", "-", "weathering"),
    "69.813": ("Oil Stains (Gloss)", "73.813", "-", "weathering"),
    "69.814": ("Fuel Stains (Gloss)", "73.814", "-", "weathering"),
    "69.817": ("Petrol Spills (Gloss)", "73.817", "-", "weathering"),
    "69.818": ("Brown Eng. Soot (Matt)", "73.818", "-", "weathering"),
    "69.821": ("Rust Texture (Matt)", "73.821", "-", "weathering"),
    # --- 5 primers ---
    "70.640": ("White Primer", "70.600", "-", "primer"),
    "70.641": ("Grey Primer", "70.601", "-", "primer"),
    "70.642": ("Black Primer", "70.602", "-", "primer"),
    "70.643": ("Ivory Primer", "70.918", "-", "primer"),
    "70.644": ("Sand Primer", "70.613", "-", "primer"),
    # --- 7 auxiliaires ---
    "69.701": ("Gloss Varnish", "-", "-", "auxiliary"),
    "69.702": ("Matt Varnish", "-", "-", "auxiliary"),
    "69.703": ("Satin Varnish", "-", "-", "auxiliary"),
    "71.261": ("Airbrush Thinner", "-", "-", "auxiliary"),
    "71.262": ("Flow Improver", "-", "-", "auxiliary"),
    "73.212": ("Decal Softener", "-", "-", "auxiliary"),
    "73.214": ("Chipping Medium", "-", "-", "auxiliary"),
}

with open(PALETTE) as f:
    pal = json.load(f)

missing = [c for c in pal if c not in DATA]
extra = [c for c in DATA if c not in pal]
assert not missing, f"Codes sans équivalence: {missing}"
assert not extra, f"Codes en trop: {extra}"

for code, (name, vmc, mrc, cat) in DATA.items():
    pal[code]["name"] = name
    pal[code]["vallejo_model_color"] = vmc
    pal[code]["mr_color"] = mrc
    pal[code]["category"] = cat

with open(PALETTE, "w") as f:
    json.dump(pal, f, indent=2, ensure_ascii=False)

# Récap par catégorie
from collections import Counter
cats = Counter(v["category"] for v in pal.values())
print("Palette enrichie:", PALETTE)
print("Total:", len(pal))
for c, n in cats.most_common():
    print(f"  {c}: {n}")
print()
print("Exemples clés:")
for code in ["69.008", "69.017", "69.054", "69.057", "69.817", "69.005"]:
    p = pal[code]
    print(f"  {code} {p['name']:24s} {p['hex']} | VMC {p['vallejo_model_color']:7s} | {p['category']}")
