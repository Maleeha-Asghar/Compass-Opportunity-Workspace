create table if not exists public.admin_users (
    user_id uuid primary key references auth.users(id) on delete cascade,
    created_at timestamptz not null default now()
);

alter table public.admin_users enable row level security;

drop policy if exists "admin users can read own membership" on public.admin_users;
create policy "admin users can read own membership"
on public.admin_users for select
to authenticated
using (auth.uid() = user_id);

create or replace function public.is_admin_user(check_user_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select exists (
        select 1
        from public.admin_users
        where user_id = check_user_id
    );
$$;

revoke all on function public.is_admin_user(uuid) from public;
grant execute on function public.is_admin_user(uuid) to authenticated;

create table if not exists public.user_opportunity_matches (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid not null references auth.users(id) on delete cascade,
    opportunity_id text not null,
    eligibility_result jsonb,
    priority text,
    priority_score numeric,
    notes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, opportunity_id)
);

create index if not exists user_opportunity_matches_user_created_idx
on public.user_opportunity_matches (user_id, created_at desc);

alter table public.user_opportunity_matches enable row level security;

drop policy if exists "user opportunity matches are private" on public.user_opportunity_matches;
create policy "user opportunity matches are private"
on public.user_opportunity_matches for all
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create table if not exists public.reminder_deliveries (
    id uuid primary key default uuid_generate_v4(),
    task_id uuid not null references public.application_tasks(id) on delete cascade,
    reminder_date date not null,
    notification_email text not null,
    sent_at timestamptz not null default now(),
    provider_response jsonb,
    unique (task_id, reminder_date, notification_email)
);

create index if not exists reminder_deliveries_sent_idx
on public.reminder_deliveries (sent_at desc);

alter table public.reminder_deliveries enable row level security;

drop policy if exists "reminder deliveries are admin only" on public.reminder_deliveries;
create policy "reminder deliveries are admin only"
on public.reminder_deliveries for select
to authenticated
using (public.is_admin_user(auth.uid()));

drop policy if exists "opportunities readable by authenticated users" on public.opportunities;
drop policy if exists "opportunities readable by admins" on public.opportunities;
drop policy if exists "opportunity sources readable by authenticated users" on public.opportunity_sources;
drop policy if exists "opportunity sources readable by admins" on public.opportunity_sources;
drop policy if exists "source pages readable by authenticated users" on public.source_pages;
drop policy if exists "source pages readable by admins" on public.source_pages;
drop policy if exists "eval runs readable by authenticated users" on public.eval_runs;
drop policy if exists "eval runs readable by admins" on public.eval_runs;
drop policy if exists "opportunity embeddings readable by authenticated users" on public.opportunity_embeddings;
drop policy if exists "opportunity embeddings readable by admins" on public.opportunity_embeddings;
drop policy if exists "api call logs readable by authenticated users" on public.api_call_logs;
drop policy if exists "api call logs readable by admins" on public.api_call_logs;
drop policy if exists "search cache readable by authenticated users" on public.search_cache;
drop policy if exists "search cache readable by admins" on public.search_cache;

create policy "opportunities readable by admins"
on public.opportunities for select
to authenticated
using (public.is_admin_user(auth.uid()));

create policy "opportunity sources readable by admins"
on public.opportunity_sources for select
to authenticated
using (public.is_admin_user(auth.uid()));

create policy "source pages readable by admins"
on public.source_pages for select
to authenticated
using (public.is_admin_user(auth.uid()));

create policy "eval runs readable by admins"
on public.eval_runs for select
to authenticated
using (public.is_admin_user(auth.uid()));

create policy "opportunity embeddings readable by admins"
on public.opportunity_embeddings for select
to authenticated
using (public.is_admin_user(auth.uid()));

create policy "api call logs readable by admins"
on public.api_call_logs for select
to authenticated
using (public.is_admin_user(auth.uid()));

create policy "search cache readable by admins"
on public.search_cache for select
to authenticated
using (public.is_admin_user(auth.uid()));
