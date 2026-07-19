---
name: hermes-cron-dispatcher
description: Internal dispatcher that lets Hermes create only Brain-confirmed cron requests.
---

# Hermes cron dispatcher

This skill is installed for the Hermes sandbox’s internal dispatcher. It claims
Brain-approved jobs from the local broker and creates them with `hermes cron
create`. Brain cannot access this command.

Each created job first runs the isolated `scout` Hermes profile for Tavily
research, then the isolated `inspector` profile to judge Scout's evidence.
Hermes synthesizes their outputs. The `scout-inspector-publisher` skill posts
the two intermediate stages through their respective Discord bots, while Sage
posts only the final report to `#daily`.
