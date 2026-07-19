-- Durable, server-side Discord feedback ledger.  This is intentionally
-- separate from episodic summaries so agents can inspect current signals.
create table if not exists public.reviews_feedback (
    id bigint generated always as identity primary key,
    event_key text not null unique,
    guild_id text,
    channel_id text not null,
    thread_id text,
    message_id text not null,
    parent_message_id text,
    author_id text,
    event_type text not null check (event_type in ('button', 'reaction', 'reply', 'thread_reply')),
    value text,
    content text,
    metadata jsonb not null default '{}'::jsonb,
    occurred_at timestamptz not null default now(),
    recorded_at timestamptz not null default now()
);

create index if not exists reviews_feedback_recent_idx
    on public.reviews_feedback (occurred_at desc);
create index if not exists reviews_feedback_message_idx
    on public.reviews_feedback (message_id, event_type);

alter table public.reviews_feedback enable row level security;
