#!/usr/bin/env bash
# IT5440 overnight queue — restart-safe.
#
#   bash run_queue.sh                  # smoke -> qwen2.5-coder:7b -> qwen3.5:9b
#   bash run_queue.sh local_qwen14b    # optional third size point
#   bash run_queue.sh local_qwen7b     # (re)run one config only
#
# An interrupted run is resumed, never restarted from zero: ccbench skips
# every job already recorded with status "ok". Logs go to logs/<name>.log.
# Run under nohup/tmux so an SSH drop does not kill it:
#   nohup bash run_queue.sh > logs/queue.out 2>&1 &
set -u
cd "$(dirname "$0")"
mkdir -p logs
cd ccbench

QUEUE=("$@")
if [ ${#QUEUE[@]} -eq 0 ]; then
  QUEUE=(local_smoke local_qwen7b local_qwen9b)
fi

OLLAMA_HOST_URL="${OLLAMA_HOST_URL:-http://localhost:11434}"

# --- preflight: server up + every needed model pulled -----------------------
tags=$(curl -sf "$OLLAMA_HOST_URL/api/tags") || {
  echo "FATAL: Ollama not reachable at $OLLAMA_HOST_URL — start it first (see SERVER_SETUP.md)"; exit 1; }
for name in "${QUEUE[@]}"; do
  cfg="configs/$name.json"
  [ -f "$cfg" ] || { echo "FATAL: missing $cfg"; exit 1; }
  models=$(python3 -c "import json,sys; print('\n'.join(m['model'] for m in json.load(open(sys.argv[1]))['models']))" "$cfg")
  for m in $models; do
    echo "$tags" | grep -q "\"$m\"" || echo "$tags" | grep -q "\"$m:latest\"" || {
      echo "FATAL: model '$m' not pulled. Run: ollama pull $m"; exit 1; }
  done
done
echo "preflight OK: $(date)"

# --- queue -------------------------------------------------------------------
for name in "${QUEUE[@]}"; do
  cfg="configs/$name.json"
  exp=$(ls -d "results/$name-"* 2>/dev/null | sort | tail -1)
  echo "=== $name start $(date) ===" | tee -a "../logs/$name.log"
  if [ -n "$exp" ]; then
    echo "resuming $exp" | tee -a "../logs/$name.log"
    python3 -m ccbench resume "$exp" 2>&1 | tee -a "../logs/$name.log"
  else
    python3 -m ccbench run "$cfg" 2>&1 | tee -a "../logs/$name.log"
  fi
  rc=${PIPESTATUS[0]}
  echo "=== $name exit=$rc $(date) ===" | tee -a "../logs/$name.log"
  if [ "$name" = "local_smoke" ]; then
    # ccbench exits 0 even when individual jobs error, so inspect the records
    smoke_exp=$(ls -d "results/$name-"* 2>/dev/null | sort | tail -1)
    python3 - "$smoke_exp" <<'PYEOF' || { echo "FATAL: smoke failed — not starting the long runs. Check logs/local_smoke.log"; exit 1; }
import json, sys, os
p = os.path.join(sys.argv[1], "results.jsonl")
latest = {}
for l in open(p):
    if l.strip():
        r = json.loads(l)
        latest[r["job_key"]] = r   # bản ghi sau cùng thắng (resume có thể ghi lại lượt lỗi)
recs = list(latest.values())
bad = [r for r in recs if r.get("status") != "ok" or not (r.get("raw_response") or "").strip()]
empty_think = [r for r in recs if (r.get("provider_extra") or {}).get("thinking_chars", 0) > 0]
print("smoke: %d records, %d bad, %d with thinking leaked" % (len(recs), len(bad), len(empty_think)))
for r in bad[:5]:
    print("  BAD", r["model_label"], r["strategy"], r.get("error"))
sys.exit(1 if bad or empty_think or len(recs) < 32 else 0)
PYEOF
  fi
done
echo "queue done $(date)"