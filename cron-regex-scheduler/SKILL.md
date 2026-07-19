---
name: cron-regex-scheduler
description: Safely parse simple natural-language schedules with regex and create confirmed Hermes cron jobs.
---

# Regex cron scheduler

Use this skill when someone asks to schedule a recurring Hermes task in plain
English. The parser accepts only these schedule formats:

- `every 15 minutes`
- `every 2 hours`
- `daily at 9am`
- `weekdays at 17:30`
- `weekly on monday at 9am`
- `monthly on day 1 at 08:00`

First parse the schedule. Do not hand-write an expression or accept arbitrary
cron syntax from a message:

```bash
/opt/hermes/.venv/bin/python /sandbox/.hermes/skills/cron-regex-scheduler/cron_parse.py "daily at 9am"
```

The result contains `cron` and `description`. All clock times are **CDT**
(UTC-5); the returned five-field expression is the UTC schedule Hermes runs.
State the parsed CDT schedule, the UTC cron expression, the time zone,
the task prompt, and the Discord delivery target. Ask for explicit confirmation
before creating or changing a job.

After confirmation, create it with a descriptive name. Hermes must do the
research itself before producing each result. Include both the `tavily-search`
and `sage-cron-publisher` skills so it researches first and Sage posts the
final report in `#daily`:

```bash
/opt/hermes/.venv/bin/hermes cron create "<cron>" "Research this task yourself with Tavily before writing the report: <self-contained task prompt>" --name "<job-name>" --deliver discord --skill tavily-search --skill sage-cron-publisher
```

Use `--deliver discord` only for messages intended for the configured Discord
delivery channel. Never place API keys, Discord tokens, database URLs, or other
secrets in the job prompt. Verify after creation:

```bash
/opt/hermes/.venv/bin/hermes cron list
```

To run a job once for a test, use `hermes cron run <job-id>` only after the
user explicitly approves the test.
