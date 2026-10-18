#!/usr/bin/env bash
# Teste le backend contre un serveur deja lance.
#   ./smoketest.sh [BASE_URL] [IMAGE]
set -u
cd "$(dirname "$0")"
BASE="${1:-http://127.0.0.1:8000}"
IMG="${2:-../output/palettes_v2/02_crapaud.png}"

echo "== /health =="; curl -s "$BASE/health"; echo
echo "== /palette (5 premiers) =="
curl -s "$BASE/palette" | python -c "import sys,json;d=json.load(sys.stdin);print('count',d['count']);[print(' ',c['code'],c['hex'],c['name']) for c in d['colors'][:5]]"
echo "== /recolor (map explicite: 02 crapaud -> 69.009) =="
curl -s -F "file=@$IMG" -F 'map=hue:5:28:69.009:1.0:sat0.35:roi0,0,1,0.68' \
     "$BASE/recolor" -o /tmp/fc_recolor.png -D /tmp/fc_recolor.hdr
echo "  png: $(wc -c < /tmp/fc_recolor.png) octets"; grep -i '^x-report' /tmp/fc_recolor.hdr
echo "== /process (auto, code seul, sans paint) =="
curl -s -F "file=@$IMG" -F 'code=69.009' -F 'do_paint=false' "$BASE/process"; echo
