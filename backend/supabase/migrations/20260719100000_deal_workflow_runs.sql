-- Immutable audit trail for Discord-triggered daily deal research.
create table if not exists public.deal_workflow_runs (
  id uuid primary key, mode text not null check (mode in ('demo', 'live')),
  started_at timestamptz not null, finished_at timestamptz not null, preferences_path text not null,
  raw_listings jsonb not null, categorized jsonb not null, recommendations jsonb not null,
  discord_delivery jsonb not null, steps jsonb not null, created_at timestamptz not null default now()
);
alter table public.deal_workflow_runs enable row level security;
create policy "authenticated users can read workflow runs" on public.deal_workflow_runs for select to authenticated using (true);
