# System status — 2026-07-18

Verified live at 2026-07-19 04:38 UTC (23:38 CDT).

## Executive state

| System | State | Evidence |
|---|---|---|
| Vercel UI | Up | `https://decision-frontier.vercel.app` returned 200 |
| Vercel API | Up | `/api/health` reached hosted Supabase |
| Supabase | Healthy | Project `qzegmkzyzalmakoqxezc`, `ca-central-1`, `ACTIVE_HEALTHY` |
| EC2 agent host | Running | `35.172.137.131`, both EC2 health checks passed |
| AutoResearch | Running | 42 measured snapshots; challenger 1 safely discarded |
| Railway coordinator | Up | `/api/status` and `/api/radar` returned 200 |
| Discord agents | Up | Brain, Scout, Inspector, and Concierge authenticated |
| Discord → daily training | Integrated here | Nightly tournament fetches real Discord exchanges and persists episodes |
| AutoResearch → Discord | Integrated here | Promotions plus every fifth checkpoint post through the Brain bot |

## What is actually running

### AWS

- EC2 `aitx-agent-host` is the always-on compute plane.
- Containers seen live: OpenShell workspace, healthy OpenClaw sandbox,
  `autoresearch`, and `search-cache`.
- `autoresearch` uses `restart=unless-stopped`.
- Host cron runs `scripts/nightly_master_cycle.py` at `05:30 UTC`.
- AutoResearch had 42 snapshots when checked. The current champion was 0.5933
  decision accuracy, 100% deal safety.
- Both security-group and NACL rules for SSH and the read-only leaderboard are
  active. `http://35.172.137.131:8787/` and `/radar` returned 200 publicly.
- AWS SSO is authenticated. The instance was relaunched at 04:11 UTC, which
  explains the stale prior IP and SSH failure.
- The merged Hermes workspace requires Git. The old bare-Python container
  failed once after the code update; Compose now installs Git and owns the
  durable `autoresearch` service. It restarted cleanly with zero restarts.
- A second Cursor-created `t3.small` (`i-0339071b78eaf53ae`,
  `107.21.178.135`) is healthy and running the same loop through systemd on a
  12 GiB volume. It is a compute-only experiment box: it has inference keys but
  no coordinator, Supabase, or Discord variables, so it does not update the
  public UI or post insights. It self-stops at 05:00 UTC on July 20.
- The canonical connected worker remains the `t3.xlarge`
  (`i-093185e0c520144b3`). The AWS budget is $15/month; AWS currently reports
  $0 actual and a $2.60 forecast.

### Railway

- Active coordinator:
  `https://nemoclaw-coordinator-api-production.up.railway.app`
- Live results at audit time: 42 radar rows, four evaluation rows, four episodic
  rows.
- The coordinator reports `idle` because `/api/status` describes its legacy
  in-process demo runner. The real AutoResearch worker runs on EC2. `/api/radar`
  is the authoritative liveness signal.
- The Railway CLI account can see two older `cursor-claude-connector` projects,
  but neither owns the active coordinator hostname. The active service is
  probably under a teammate's Railway project. It is reachable but not
  manageable from this login.
- Railway storage is ephemeral. A test episode POST returned 200, then a later
  read returned the original four rows. EC2 now replace-syncs durable radar
  history, while Supabase is authoritative for episodes and daily runs.

### Supabase

Live counts when audited:

| Table | Rows |
|---|---:|
| `listings` | 15 |
| `sources` | 6 |
| `sync_runs` | 6 |
| `rsi_runs` | 1 |
| `episodes` | 15 after integration test |
| `search_cache` | 1 |

The initial zero episode count exposed the missing Discord persistence path.
The end-to-end test then wrote 15 real Discord episodes: one approved and 14
neutral. No local migration was used.

### Vercel and UI

- Public deployment: `https://decision-frontier.vercel.app`
- Marketplace cards use hosted Supabase. The GPU endpoint returned three live
  Best Buy rows.
- The merged Cursor leaderboard adds Karpathy-style keep/discard charts.
- The API now prefers Railway's live radar history and falls back to committed
  evidence only when the coordinator is unavailable.
- Playwright verified both Leaderboard and Methodology with live data, autoplay,
  zoom/fullscreen controls, and no application JavaScript errors. The new
  21.5-second recording is `dashboard/media/rsi-05-autoresearch-progress.mp4`.
- `/api/radar`, `/api/autoresearch-status`, `/api/evaluations`, and
  `/api/episodic-memory` are read-only Vercel proxies to Railway.

### Discord

- Brain, Scout, Inspector, and Concierge all authenticate successfully.
- `#daily` contains current GPU research from the agents.
- No webhook is required. Bot-token REST calls already cover:
  - reading human prompts, agent replies, and reactions;
  - posting AutoResearch promotions/checkpoints;
  - posting daily tournament results and weekly review requests.
- A webhook is only useful if an external system must post without a bot token.
- The audit posted a real measured checkpoint to `#daily` at 04:17 UTC:
  accuracy 0.5933, retrieval 2.82s, safety 100%.

## Seven-step AutoResearch loop

1. **Pull Digest** — the 05:30 UTC cron reads live `MEMORY.md`, sandbox episodes,
   and recent Discord conversations.
2. **Recall Ideas** — yesterday's champion plus durable prior results supply the
   starting policies.
3. **Generate Routes** — evaluate control, episodic memory, exemplar-SFT, and
   the current AutoResearch champion.
4. **Verify Candidates** — the frozen golden set measures accuracy, retrieval
   time, price/deal safety, and agent regression.
5. **Select Strategy** — the Pareto gate rejects unsafe, slow, degraded, or
   under-sampled candidates.
6. **Promote Daily** — the winner becomes the live sandbox `MEMORY.md`; metrics
   go to Railway, Supabase, the UI, and Discord.
7. **Weekly Feedback** — Sunday synthesis asks the human for approval or
   corrections; that feedback becomes the next digest.

## Cursor and Claude integration

- Cursor's functional work is integrated: the dedicated worker Terraform,
  Prime evaluation demo, PC-only golden-set correction, and design-QA evidence.
- Claude's resource work is integrated: EC2 lifecycle protection, Supabase
  read-only tooling, Sage cron publishing, and the coordinator/UI data paths.
- The later `restructure/clean-layout` branch was audited but not deployed. It
  moves every runtime path and drops the Discord-to-Supabase seven-step additions
  from `nightly_master_cycle.py`; merging it during a live run would break the
  Vercel, cron, and EC2 paths. Its useful functional commit was cherry-picked
  without the risky repository-wide rename.

## Communication map

```text
Discord ──read──▶ nightly tournament ──evaluate──▶ Verifiers/Nemotron
   ▲                     │                              │
   │                     ├──write──▶ Supabase           │
   │                     └──promote─▶ OpenClaw MEMORY.md│
   │                                                    │
   └──insights──────── AutoResearch on EC2 ──snapshots──▶ Railway
                                                        │
                                                        ▼
                                                  Vercel UI/API
```

## Operator checks

```bash
# Public UI and live database
curl -fsS https://decision-frontier.vercel.app/api/health
curl -fsS 'https://decision-frontier.vercel.app/api/marketplace?category=gpu'

# AutoResearch public data plane
curl -fsS https://nemoclaw-coordinator-api-production.up.railway.app/api/radar

# AWS control-plane access (login only when the SSO session expires)
aws ec2 describe-instances --profile dev_sso_giftmaxxing \
  --filters Name=tag:Name,Values=aitx-agent-host
```
