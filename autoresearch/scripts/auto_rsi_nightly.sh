#!/usr/bin/env bash
# Nightly RSI evaluation cycle (EC2 host cron, 05:30 UTC — right after
# the 05:00 memory distillation):
#   1. snapshot tonight's lessons out of the sandbox
#   2. vf-eval rollouts with lessons injected (memory ON)
#   3. append the measured challenger with accepted=false
#   4. request a human promote/keep decision in Discord
# The cron never changes the champion.
set -euo pipefail
exec >> /opt/aitx/rsi-cycles.log 2>&1
echo "=== RSI cycle $(date -u +%FT%TZ) ==="

REPO=/opt/aitx/repo
cd "$REPO"
set -a; . nemotron/deploy/docker-compose/.env; set +a
export OPENAI_API_KEY="${NVIDIA_INFERENCE_API_KEY:?}"
export GOLDEN_DATASET="$REPO/autoresearch/scripts/golden_dataset.json"
export PATH="/root/.local/bin:$PATH"

C=$(docker ps --format '{{.Names}}' | grep openshell- | head -1)
[ -n "$C" ] || { echo "no sandbox running; abort"; exit 1; }

mkdir -p /opt/aitx/memory
VERSION="auto-$(date -u +%Y%m%d)"
LESSONS=/opt/aitx/memory/lessons-$VERSION.md

docker cp "$C:/sandbox/.openclaw/workspace/MEMORY.md" "$LESSONS" 2>/dev/null || echo "" > "$LESSONS"
echo "lessons snapshot: $LESSONS ($(wc -l < "$LESSONS") lines)"

cd "$REPO/autoresearch/environments/gpu_deal_judge"
uv run --with verifiers --with . vf-eval gpu-deal-judge \
  -m "nvidia/nemotron-3-super-120b-a12b" \
  -b "https://integrate.api.nvidia.com/v1" -k OPENAI_API_KEY \
  -n 15 -r 3 -s --env-args "{\"memory_file\": \"$LESSONS\"}" || { echo "eval failed"; exit 1; }

RESULTS=$(ls -t "$PWD"/outputs/evals/*/*/results.jsonl | head -1)

# NVIDIA rate-limit fallback: if most rollouts errored, rerun via OpenRouter
# with the same model (id identical for Super) before recording anything.
VALID=$(python3 -c "import json,sys; r=[json.loads(l) for l in open('$RESULTS') if l.strip()]; print(sum(1 for x in r if not x.get('error')), len(r))")
if [ "$(echo "$VALID" | awk '{print ($2>0 && $1*10 < $2*6) ? 1 : 0}')" = "1" ] && [ -n "${OPENROUTER_API_KEY:-}" ]; then
  echo "NVIDIA eval degraded ($VALID valid/total) — falling back to OpenRouter"
  OPENAI_API_KEY="$OPENROUTER_API_KEY" uv run --with verifiers --with . vf-eval gpu-deal-judge \
    -m "nvidia/nemotron-3-super-120b-a12b" \
    -b "https://openrouter.ai/api/v1" -k OPENAI_API_KEY \
    -n 15 -r 3 -s --env-args "{\"memory_file\": \"$LESSONS\"}" \
    && RESULTS=$(ls -t "$PWD"/outputs/evals/*/*/results.jsonl | head -1) \
    && echo "using OpenRouter results: $RESULTS" \
    || echo "OpenRouter fallback also failed; keeping NVIDIA results"
fi
cd "$REPO/autoresearch"
python3 scripts/verifiers_to_rsi_csv.py "$RESULTS" \
  --output data/rsi_runs.csv \
  --run-id "$VERSION-$(date -u +%H%M)" \
  --version "$VERSION" \
  --parent-version "$(python3 -c 'import csv; r=list(csv.DictReader(open("data/rsi_runs.csv"))); print(next(x["version"] for x in reversed(r) if x["current"]=="true"))')" \
  --policy-change "Nightly lessons $(date -u +%F)" \
  --teacher-model Nemotron \
  --accepted false \
  --current false
# Durable store: write the run + tonight's episodes to Supabase (survives
# Railway redeploys and the EC2 self-stop). Failures never break the cycle.
if [ -n "${SUPABASE_DB_PW:-}" ] && command -v psql >/dev/null; then
  DSN="host=${SUPABASE_POOLER_HOST:-aws-0-ca-central-1.pooler.supabase.com} port=5432 dbname=postgres user=${SUPABASE_POOLER_USER:-postgres.qzegmkzyzalmakoqxezc} sslmode=require"
  docker cp "$C:/sandbox/.openclaw/workspace/memory/episodes.jsonl" /tmp/episodes.jsonl 2>/dev/null || : > /tmp/episodes.jsonl
  python3 - "$RESULTS" "$VERSION" > /tmp/rsi-supabase.sql <<'PYEOF'
import json, sys, uuid
def q(s):
    tag = "q" + uuid.uuid4().hex[:8]
    return f"${tag}${s}${tag}$"
rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
valid = [r for r in rows if not r.get("error")]
rw = [float(r.get("reward", 0)) for r in valid] or [0]
print(f"""insert into public.rsi_runs (run_id, version, decision_quality, n_valid, n_total, decision)
values ({q(sys.argv[2] + '-' + uuid.uuid4().hex[:6])}, {q(sys.argv[2])}, {sum(rw)/len(rw):.4f}, {len(valid)}, {len(rows)}, {q('candidate')})
on conflict (run_id) do nothing;""")
for line in open("/tmp/episodes.jsonl"):
    line = line.strip()
    if not line:
        continue
    try:
        e = json.loads(line)
    except json.JSONDecodeError:
        continue
    qual = e.get("quality") if e.get("quality") in ("good", "bad", "neutral") else None
    print(f"""insert into public.episodes (episode_id, episode_date, channel, task_type, request, agent_chain, outcome, feedback, quality, lesson)
values ({q(str(e.get('episode_id', uuid.uuid4().hex)))}, nullif({q(str(e.get('date', '')))}, '')::date, {q(str(e.get('channel', '')))}, {q(str(e.get('task_type', '')))}, {q(str(e.get('request', '')))}, {q(json.dumps(e.get('agent_chain', [])))}::jsonb, {q(str(e.get('outcome', '')))}, {q(json.dumps(e.get('feedback', {})))}::jsonb, {q(qual) if qual else 'null'}, {q(str(e.get('lesson', ''))) if e.get('lesson') else 'null'})
on conflict (episode_id) do nothing;""")
PYEOF
  PGPASSWORD="$SUPABASE_DB_PW" psql "$DSN" -q -v ON_ERROR_STOP=0 -f /tmp/rsi-supabase.sql >/dev/null 2>&1 \
    && echo "supabase: run + episodes stored" || echo "supabase write failed (non-fatal)"
  rm -f /tmp/rsi-supabase.sql
fi

python3 scripts/post_rsi_discord.py

# Optional: log this cycle to the coordinator API so both RSI tracks share
# one pane of glass. Failures never break the cycle. COORDINATOR_TOKEN adds
# the bearer header once the Railway service sets one.
if [ -n "${COORDINATOR_URL:-}" ]; then
  AUTH=(); [ -n "${COORDINATOR_TOKEN:-}" ] && AUTH=(-H "Authorization: Bearer $COORDINATOR_TOKEN")
  python3 - "$RESULTS" "$VERSION" <<'PYEOF' > /tmp/rsi-eval-post.json
import json,sys
rows=[json.loads(l) for l in open(sys.argv[1]) if l.strip()]
valid=[r for r in rows if not r.get("error")]
rw=[float(r.get("reward",0)) for r in valid] or [0]
print(json.dumps({"version":sys.argv[2],"source":"ec2-episodic-memory-track",
  "decision_quality":round(sum(rw)/len(rw),4),"n_valid":len(valid),"n_total":len(rows)}))
PYEOF
  curl -s -m 15 "${AUTH[@]}" -H "Content-Type: application/json" \
    -d @/tmp/rsi-eval-post.json "${COORDINATOR_URL%/}/api/evaluations" >/dev/null \
    && echo "coordinator: eval row uploaded" || echo "coordinator unreachable (non-fatal)"
  EPISODES=/tmp/rsi-episodes-post.json
  docker cp "$C:/sandbox/.openclaw/workspace/memory/episodes.jsonl" /tmp/episodes.jsonl 2>/dev/null && \
    python3 -c "import json,sys; rows=[json.loads(l) for l in open('/tmp/episodes.jsonl') if l.strip()]; json.dump(rows[-20:], open('$EPISODES','w'))" && \
    curl -s -m 15 "${AUTH[@]}" -H "Content-Type: application/json" \
      -d @"$EPISODES" "${COORDINATOR_URL%/}/api/episodic-memory" >/dev/null \
    && echo "coordinator: recent episodes uploaded" || echo "coordinator episodes upload skipped"
fi
echo "candidate recorded; champion unchanged pending a human Discord decision"
