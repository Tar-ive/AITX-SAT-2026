# Daily Discord deals workflow

In `#gpu-desk`, send Brain `!deals daily at 9am`. Brain parses the command with
the repository's regex-only scheduler and queues the resulting Hermes job.
Hermes invokes the workflow once per day: OpenShell dispatches
specialist Hermes agents, HiddenLayer supplies the protected research boundary,
results are normalized into `online` and `offline`, and recommendations are
ranked against `user.md`. Sage publishes the final linked digest to `#daily`
without an internal run ID.

Every run writes `workflow/runs/<uuid>.json` with UTC timestamps and per-step
durations, then mirrors the same immutable payload to Supabase when its service
role credentials are configured. The two-minute demo uses fixtures and never
contacts Discord, OpenShell, HiddenLayer, or a retailer.

## Run it now

```powershell
python workflow/daily_deals.py '!deals daily at 9am'
python workflow/daily_deals.py --run --mode demo
python -m unittest workflow/test_workflow.py
```

## Production handoff

1. Apply `backend/supabase/migrations/20260719100000_deal_workflow_runs.sql`.
2. Edit `workflow/user.md` with the user's actual constraints.
3. Configure `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
   `DISCORD_DAILY_WEBHOOK_URL`, and `OPEN_SHELL_RESEARCH_COMMAND` outside the
   repository. The OpenShell command must return normalized listing JSON.
4. Have the Discord bot pass the exact message text to `daily_deals.py`; after
   preview/confirmation, create the Hermes cron job with the existing
   `cron-regex-scheduler` and `hermes-cron-dispatcher` skills.
5. Use `--mode live` only after the Discord channel and agent permissions are
   verified. No workflow step can make a purchase.

## Two-minute reproducible demo

Run the three commands above. The first prints a UTC cron expression, the
second generates a fully timestamped ledger and a dry-run `#daily` message,
and the third verifies schedule parsing and online/offline ranking. Re-running
the demo creates a new immutable ledger while retaining the same fixture input.
