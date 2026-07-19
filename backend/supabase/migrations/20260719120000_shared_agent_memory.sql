-- Shared, sanitised user context for NemoHermes and NemoClaw.
-- This is retrieval/training-corpus input, not automatic model-weight training.
create table if not exists public.agent_shared_memory (
    id bigint generated always as identity primary key,
    event_key text not null unique,
    source_agent text not null check (source_agent in ('nemohermes', 'nemoclaw', 'sage')),
    guild_id text,
    channel_id text,
    message_id text,
    author_id text,
    input_text text not null,
    created_at timestamptz not null default now()
);

create index if not exists agent_shared_memory_recent_idx
    on public.agent_shared_memory (created_at desc);

alter table public.agent_shared_memory enable row level security;
