create extension if not exists pgcrypto;

create table public.sources (
  id smallint generated always as identity primary key,
  slug text not null unique check (slug ~ '^[a-z0-9_-]+$'),
  name text not null,
  source_type text not null check (source_type in ('marketplace', 'retailer', 'catalog', 'search')),
  homepage_url text not null,
  requires_credentials boolean not null default true,
  enabled boolean not null default false,
  created_at timestamptz not null default now()
);

create table public.products (
  id uuid primary key default gen_random_uuid(),
  category text not null,
  brand text,
  model text,
  mpn text,
  gtin text,
  canonical_name text not null,
  specs jsonb not null default '{}'::jsonb check (jsonb_typeof(specs) = 'object'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.product_identifiers (
  source_id smallint not null references public.sources(id),
  external_id text not null,
  product_id uuid not null references public.products(id) on delete cascade,
  source_url text,
  primary key (source_id, external_id)
);

create table public.listings (
  id uuid primary key default gen_random_uuid(),
  source_id smallint not null references public.sources(id),
  external_id text not null,
  product_id uuid references public.products(id) on delete set null,
  title text not null,
  condition text,
  seller_name text,
  seller_rating numeric check (seller_rating between 0 and 100),
  currency text not null default 'USD' check (currency ~ '^[A-Z]{3}$'),
  item_price numeric(12,2) not null check (item_price >= 0),
  shipping_price numeric(12,2) not null default 0 check (shipping_price >= 0),
  total_price numeric(12,2) generated always as (item_price + shipping_price) stored,
  listing_url text not null,
  image_url text,
  availability text,
  raw_payload jsonb not null default '{}'::jsonb check (jsonb_typeof(raw_payload) = 'object'),
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  expires_at timestamptz,
  unique (source_id, external_id)
);

create table public.price_observations (
  id bigint generated always as identity primary key,
  listing_id uuid not null references public.listings(id),
  item_price numeric(12,2) not null check (item_price >= 0),
  shipping_price numeric(12,2) not null default 0 check (shipping_price >= 0),
  total_price numeric(12,2) generated always as (item_price + shipping_price) stored,
  currency text not null default 'USD' check (currency ~ '^[A-Z]{3}$'),
  observed_at timestamptz not null default now()
);

create table public.watchlists (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  query text not null,
  category text,
  target_price numeric(12,2) check (target_price >= 0),
  currency text not null default 'USD' check (currency ~ '^[A-Z]{3}$'),
  cadence text not null default 'daily' check (cadence in ('hourly', 'daily', 'weekly')),
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.sync_runs (
  id bigint generated always as identity primary key,
  source_id smallint not null references public.sources(id),
  status text not null check (status in ('running', 'succeeded', 'failed')),
  records_seen integer not null default 0 check (records_seen >= 0),
  error_message text,
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
  started_at timestamptz not null default now(),
  finished_at timestamptz
);

create index listings_product_price_idx on public.listings (product_id, total_price);
create index listings_source_seen_idx on public.listings (source_id, last_seen_at desc);
create index price_observations_listing_time_idx on public.price_observations (listing_id, observed_at desc);
create index watchlists_user_idx on public.watchlists (user_id) where enabled;

create function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger products_set_updated_at
before update on public.products
for each row execute function public.set_updated_at();

create trigger watchlists_set_updated_at
before update on public.watchlists
for each row execute function public.set_updated_at();

alter table public.sources enable row level security;
alter table public.products enable row level security;
alter table public.product_identifiers enable row level security;
alter table public.listings enable row level security;
alter table public.price_observations enable row level security;
alter table public.watchlists enable row level security;
alter table public.sync_runs enable row level security;

create policy "authenticated users can read sources"
on public.sources for select to authenticated using (true);

create policy "authenticated users can read products"
on public.products for select to authenticated using (true);

create policy "authenticated users can read product identifiers"
on public.product_identifiers for select to authenticated using (true);

create policy "authenticated users can read listings"
on public.listings for select to authenticated using (true);

create policy "authenticated users can read price history"
on public.price_observations for select to authenticated using (true);

create policy "users manage their own watchlists"
on public.watchlists for all to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

insert into public.sources (slug, name, source_type, homepage_url, requires_credentials)
values
  ('ebay', 'eBay', 'marketplace', 'https://www.ebay.com', true),
  ('bestbuy', 'Best Buy', 'retailer', 'https://www.bestbuy.com', true),
  ('amazon', 'Amazon Creators API', 'marketplace', 'https://www.amazon.com', true),
  ('openicecat', 'Open Icecat', 'catalog', 'https://icecat.com', true),
  ('wikidata', 'Wikidata', 'catalog', 'https://www.wikidata.org', false),
  ('pcpartpicker', 'PCPartPicker (links only)', 'search', 'https://pcpartpicker.com', false);
