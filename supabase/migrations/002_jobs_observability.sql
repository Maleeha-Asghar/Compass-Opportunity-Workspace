create table if not exists public.search_jobs (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid not null references auth.users(id) on delete cascade,
    query text not null,
    profile jsonb not null default '{}'::jsonb,
    status text not null default 'queued' check (status in ('queued', 'running', 'completed', 'failed')),
    progress_message text,
    result jsonb,
    error text,
    created_at timestamptz not null default now(),
    started_at timestamptz,
    completed_at timestamptz,
    updated_at timestamptz not null default now()
);

create index if not exists search_jobs_user_created_idx
on public.search_jobs (user_id, created_at desc);

create table if not exists public.api_call_logs (
    id uuid primary key default uuid_generate_v4(),
    provider text not null,
    endpoint text not null,
    model text,
    status_code integer,
    latency_ms integer,
    success boolean not null default false,
    error_message text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists api_call_logs_provider_created_idx
on public.api_call_logs (provider, created_at desc);

create table if not exists public.search_cache (
    query text primary key,
    provider text not null,
    results jsonb not null default '[]'::jsonb,
    fetched_at timestamptz not null default now(),
    expires_at timestamptz not null
);

create index if not exists search_cache_expires_idx
on public.search_cache (expires_at);

alter table public.search_jobs enable row level security;
alter table public.api_call_logs enable row level security;
alter table public.search_cache enable row level security;

drop policy if exists "search jobs are private" on public.search_jobs;
create policy "search jobs are private"
on public.search_jobs for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists "api call logs readable by authenticated users" on public.api_call_logs;
create policy "api call logs readable by authenticated users"
on public.api_call_logs for select
to authenticated
using (true);

drop policy if exists "search cache readable by authenticated users" on public.search_cache;
create policy "search cache readable by authenticated users"
on public.search_cache for select
to authenticated
using (true);
