#!/usr/bin/env bash
# Runs once when the Codespace is created. Brings up SearXNG + Firecrawl and
# publishes a small status HTTP service on port 8081 so the outside world can
# check deployment health without needing SSH.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY="$ROOT/deploy"
LOG="$DEPLOY/bootstrap.log"
STATUS="$DEPLOY/status.json"

mkdir -p "$DEPLOY"
: > "$LOG"
exec > >(tee -a "$LOG") 2>&1

echo "[bootstrap] start $(date -u +%FT%TZ)"

for i in $(seq 1 30); do
  if docker info >/dev/null 2>&1; then break; fi
  echo "[bootstrap] waiting for docker (${i}/30)"
  sleep 2
done

if ! docker info >/dev/null 2>&1; then
  echo '{"ok":false,"stage":"docker","error":"docker daemon unavailable"}' > "$STATUS"
  exit 1
fi

cd "$DEPLOY"
echo "[bootstrap] pulling images"
docker compose pull

echo "[bootstrap] starting stack"
docker compose up -d

# Poll for SearXNG JSON API and Firecrawl API readiness.
SEARX_OK=0
FC_OK=0
for i in $(seq 1 90); do
  code_s=$(curl -s -o /dev/null -w '%{http_code}' 'http://127.0.0.1:8080/search?q=test&format=json' || true)
  code_f=$(curl -s -o /dev/null -w '%{http_code}' 'http://127.0.0.1:3002/health' || true)
  if [ "$code_s" = "200" ]; then SEARX_OK=1; fi
  if [ "$code_f" = "200" ] || [ "$code_f" = "404" ]; then FC_OK=1; fi
  if [ "$SEARX_OK" = "1" ] && [ "$FC_OK" = "1" ]; then break; fi
  if [ $((i % 10)) -eq 0 ]; then
    echo "[bootstrap] waiting for services searx=$code_s firecrawl=$code_f (${i}/90)"
  fi
  sleep 5
done

python3 - "$STATUS" "$SEARX_OK" "$FC_OK" <<'PY'
import json, sys, datetime
path, sx, fc = sys.argv[1], sys.argv[2], sys.argv[3]
data = {
    "ok": sx == "1" and fc == "1",
    "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "searxng_json_api": sx == "1",
    "firecrawl_api": fc == "1",
    "endpoints_inside_codespace": {
        "searxng": "http://127.0.0.1:8080/search?q=test&format=json",
        "firecrawl": "http://127.0.0.1:3002/v0/search",
    },
}
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(json.dumps(data, ensure_ascii=False))
PY

echo "[bootstrap] starting status server on 8081"
nohup python3 "$DEPLOY/status_server.py" > "$DEPLOY/status_server.log" 2>&1 &
echo "[bootstrap] done $(date -u +%FT%TZ)"
