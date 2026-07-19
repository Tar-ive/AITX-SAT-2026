alter table public.listings
  add column collection_method text not null default 'api'
    check (collection_method in ('api', 'scraped', 'search', 'manual')),
  add column collector text;
