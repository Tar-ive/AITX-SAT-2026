# AGENTS.md

## Cursor Cloud specific instructions

This repo is a Python monorepo (Python 3.12, pinned in `.python-version`). See `README.md`
for the product overview and the EC2 → Railway → Vercel → Supabase data plane. Notes below
are the non-obvious things needed to run/test locally in the Cloud Agent VM.

### Dependencies
- The startup update script installs Python deps with `pip install --break-system-packages -r requirements.txt`.
  A virtualenv is **not** used here: `python3 -m venv` fails on this VM (`ensurepip` missing and
  `python3.12-venv` has no apt install candidate), so packages are installed to the user site.
- `requirements.txt` (`requests`, `psycopg2-binary`) covers all runnable services and the harness.
  `matplotlib`/`numpy` (listed in `autoresearch/pyproject.toml`) are only needed for
  `autoresearch/analysis.ipynb`; install them ad hoc if you touch the notebook.

### Services (all runnable locally, no build step)
- **Railway coordinator** — `PORT=8080 python3 nemoclaw/scripts/nemotron_coordinator.py`.
  Listens on `0.0.0.0:$PORT` (default 8080). Runs with **mock verdicts + simulated iterations**;
  needs **no credentials**. Serves `/api/status`, `/api/radar`, `/api/evaluations`, `/autoresearch`.
  This is the process the root `Procfile` / `railway.toml` start in production.
- **Dashboard API + static frontend** — `COORDINATOR_URL=http://127.0.0.1:8080 python3 backend/scripts/dashboard_api.py`.
  Listens on `127.0.0.1:8787`, serves the `frontend/` UI at `/` and the `/api/*` routes.
  Gotcha: `COORDINATOR_URL` defaults to the **production Railway URL**; point it at the local
  coordinator (as above) when running both locally. `/api/marketplace`, `/api/improvement`,
  `/api/rsi-operations`, `/api/rsi-ideas` render without extra setup; DB-heavy routes need Supabase (below).
- **Autoresearch harness** (`autoresearch/`, the core product) —
  `cd autoresearch && python3 prepare.py --smoke` (no network/keys) validates the frozen harness.
  `python3 train.py --describe "..." --write-policy` runs one live experiment; it needs a **valid**
  inference key (`NVIDIA_INFERENCE_API_KEY` or `NVIDIA_API_KEY`, with `OPENROUTER_API_KEY` fallback).
  `train.py` writes `autoresearch/results.tsv` and `autoresearch/research/champion-lessons.md`;
  `git checkout --` those if you were only smoke-testing.

### Tests / lint
- Tests: `cd autoresearch/skill && python3 test_integration.py` (45 unittest cases; passes with only
  benign `ResourceWarning`s).
- There is **no lint config** in the repo (no ruff/flake8/pylint/black/eslint).

### Credentials & data-state caveats
- Secrets are injected as env vars (e.g. `NVIDIA_API_KEY`, `OPENROUTER_API_KEY`, `SUPABASE_DB_PW`,
  `SUPABASE_CONNECTION_STRING`, `DISCORD_BOT_TOKEN`). The dashboard reads `.env` via `AITX_ENV_FILE`.
- The connected Supabase project may be missing the `backend/supabase/` migration tables. When
  `public.evaluation_samples` / related tables are absent, `/api/autoresearch-experiments` and
  `/api/research-evidence` return 503 and the dashboard **Evals** page shows a SQL
  `relation "..." does not exist` error. This is expected until migrations are applied; the rest of
  the dashboard is unaffected.
- The `train.py` live eval only scores if the inference keys are valid (NVIDIA endpoint returns 403 /
  OpenRouter 401 when a key is expired). The harness/loop machinery still runs and reports metrics.
