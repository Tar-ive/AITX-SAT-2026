-- Agent SOUL memory, persisted + shareable (Hermes ↔ RSI integration).
-- Hermes learns user preferences and writes them into its SOUL.md. That file
-- is trapped in the sandbox; this table makes it persistent, web-accessible,
-- and readable by other agents — and its version history feeds the RSI loop's
-- 5th metric (episodic-memory / soul diff lines = how much the agent learned).

create table if not exists public.agent_soul (
    id bigint generated always as identity primary key,
    agent_name text not null,              -- 'hermes', 'openclaw', ...
    version integer not null default 1,
    soul_md text not null,                 -- full SOUL.md content at this version
    diff_lines integer not null default 0, -- lines changed vs previous version
    summary text,                          -- one-line what-changed (user preference learned)
    updated_at timestamptz not null default now(),
    unique (agent_name, version)
);

create index if not exists agent_soul_latest_idx
    on public.agent_soul (agent_name, version desc);

-- Latest SOUL per agent, for other agents / the web to read cheaply.
create or replace view public.agent_soul_latest as
select distinct on (agent_name) agent_name, version, soul_md, diff_lines, summary, updated_at
from public.agent_soul
order by agent_name, version desc;

alter table public.agent_soul enable row level security;
