-- Link every harness experiment to the evidence and test that produced it.
alter table public.harness_experiments
  add column if not exists evidence_episode_ids text[] not null default '{}',
  add column if not exists research_urls text[] not null default '{}',
  add column if not exists user_preference text,
  add column if not exists test_method text,
  add column if not exists metadata jsonb not null default '{}'::jsonb;

create index if not exists harness_experiments_evidence_idx
  on public.harness_experiments using gin (evidence_episode_ids);
