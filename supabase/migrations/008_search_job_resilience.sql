alter table public.search_jobs
    add column if not exists current_stage text,
    add column if not exists stage_payload jsonb not null default '{}'::jsonb,
    add column if not exists attempt_count integer not null default 0,
    add column if not exists cancelled_at timestamptz;

alter table public.search_jobs
    drop constraint if exists search_jobs_status_check;

alter table public.search_jobs
    add constraint search_jobs_status_check
    check (status in ('queued', 'running', 'completed', 'failed', 'cancelled'));

create index if not exists search_jobs_status_updated_idx
on public.search_jobs (status, updated_at);
