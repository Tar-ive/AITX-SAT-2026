-- Durable stores for the RSI loop: episodic memory + nightly evaluation runs.
-- Written by the EC2 nightly cycle (service connection); survives Railway
-- redeploys and the EC2 self-stop. Server-only: RLS enabled, no public
-- policies — the service-role connection bypasses RLS by design.

create table if not exists public.episodes (
    id bigint generated always as identity primary key,
    episode_id text not null unique,
    episode_date date,
    channel text,
    task_type text,
    request text,
    agent_chain jsonb,
    outcome text,
    feedback jsonb,
    quality text check (quality in ('good', 'bad', 'neutral')),
    lesson text,
    inserted_at timestamptz not null default now()
);

create table if not exists public.rsi_runs (
    id bigint generated always as identity primary key,
    run_id text not null unique,
    version text,
    source text not null default 'ec2-episodic-memory-track',
    decision_quality numeric,
    n_valid integer,
    n_total integer,
    decision text,
    evaluated_at timestamptz not null default now()
);

alter table public.episodes enable row level security;
alter table public.rsi_runs enable row level security;
