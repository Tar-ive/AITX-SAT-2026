-- Smart re-search cache: episodic memory applied to retrieval.
-- The agent logs every product search here; on a repeat request it checks this
-- first and re-verifies only the sites that had results last time, escalating
-- to a full search only if the price moved > threshold or the item is gone.

create table if not exists public.search_cache (
    id bigint generated always as identity primary key,
    product_query text not null,
    product_slug text not null,
    sites_checked text[] not null default '{}',
    sites_with_results text[] not null default '{}',
    best_price numeric(12,2),
    best_source text,
    best_url text,
    available boolean not null default true,
    searched_by text,
    searched_at timestamptz not null default now()
);

create index if not exists search_cache_slug_idx
    on public.search_cache (product_slug, searched_at desc);

alter table public.search_cache enable row level security;
