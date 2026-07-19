# NemoClaw skills

All deployable agent skills live here. Runtime installers copy each directory
to `/sandbox/.hermes/skills/<skill-name>` or the equivalent OpenClaw path.

| Group | Skills |
|---|---|
| Research | `database-first-research`, `hermes-tavily-search`, `supabase-readonly` |
| Scheduling | `brain-cron-coordinator`, `cron-regex-scheduler`, `hermes-cron-dispatcher` |
| Discord | `hermes-discord-audit-format`, `hermes-discord-feedback`, `sage-cron-publisher` |
| Memory and handoff | `hermes-episode-writer`, `hermes-single-conversation`, `scout-inspector-publisher` |
| Product workflow | `nemohermes-gpu-desk` |

Agent identities are in `nemoclaw/agents/`; the active Hermes policy is in
`nemoclaw/policies/hermes/SOUL.md`.
