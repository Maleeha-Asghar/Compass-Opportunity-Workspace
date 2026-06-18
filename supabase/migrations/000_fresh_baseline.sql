-- Fresh squash baseline for future repos.
-- This file reflects the current final schema state and is meant for a brand-new reset,
-- not for rewriting the already-applied migration history in this repository.

create extension if not exists "uuid-ossp";
create extension if not exists vector;

create table if not exists public.student_profiles (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid not null references auth.users(id) on delete cascade,
    compass_user_id text unique,
    full_name text,
    country text,
    degree text,
    field text,
    semester text,
    cgpa numeric(3,2),
    skills text[] not null default '{}',
    preferred_countries text[] not null default '{}',
    preferred_regions text[] not null default '{}',
    preferred_opportunity_types text[] not null default '{}',
    budget_preference text,
    ielts_status text,
    gre_status text,
    career_goal text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id)
);

create table if not exists public.opportunities (
    id uuid primary key default uuid_generate_v4(),
    public_code varchar(8) not null unique,
    title text not null,
    provider text,
    country text,
    opportunity_type text not null default 'other' check (
        opportunity_type in ('masters','internship','scholarship','fellowship','assistantship','research','other')
    ),
    deadline date,
    funding_type text,
    eligibility text[] not null default '{}',
    required_documents text[] not null default '{}',
    application_url text,
    contact_email text,
    summary text,
    payment_requested boolean not null default false,
    warnings text[] not null default '{}',
    extraction_notes text[] not null default '{}',
    verification jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.opportunity_sources (
    id uuid primary key default uuid_generate_v4(),
    opportunity_id uuid not null references public.opportunities(id) on delete cascade,
    url text not null,
    source_tier text not null check (source_tier in ('A','B','C','D')),
    content_type text not null,
    extraction_status text not null,
    notes text,
    created_at timestamptz not null default now(),
    unique (opportunity_id, url)
);

create table if not exists public.saved_opportunities (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid not null references auth.users(id) on delete cascade,
    opportunity_id uuid not null references public.opportunities(id) on delete cascade,
    created_at timestamptz not null default now(),
    unique (user_id, opportunity_id)
);

create table if not exists public.application_tasks (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid not null references auth.users(id) on delete cascade,
    opportunity_id uuid references public.opportunities(id) on delete cascade,
    title text not null,
    next_task text,
    due_date date,
    status text not null default 'pending',
    created_at timestamptz not null default now()
);

create table if not exists public.notification_preferences (
    user_id uuid primary key references auth.users(id) on delete cascade,
    email_enabled boolean not null default true,
    notification_email text,
    reminder_days integer[] not null default '{15,7,3,1,0}',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.generated_documents (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid not null references auth.users(id) on delete cascade,
    opportunity_id uuid references public.opportunities(id) on delete set null,
    document_type text not null,
    content text not null,
    grounding_flags text[] not null default '{}',
    parent_document_id uuid references public.generated_documents(id) on delete set null,
    version_number integer not null default 1,
    regeneration_instruction text,
    source_upload_id uuid references public.uploaded_files(id) on delete set null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists generated_documents_parent_idx on public.generated_documents (parent_document_id, version_number desc);
create index if not exists generated_documents_source_upload_idx on public.generated_documents (source_upload_id);

create table if not exists public.uploaded_files (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid not null references auth.users(id) on delete cascade,
    bucket text not null,
    path text not null,
    original_filename text,
    mime_type text not null,
    size_bytes integer not null,
    purpose text not null,
    extracted_text text,
    extracted_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    unique (bucket, path)
);

create table if not exists public.source_pages (
    id uuid primary key default uuid_generate_v4(),
    url text not null unique,
    content_type text not null,
    source_tier text not null,
    text text,
    fetched_at timestamptz not null default now(),
    expires_at timestamptz not null
);

create table if not exists public.eval_runs (
    id uuid primary key default uuid_generate_v4(),
    model_name text not null,
    extraction_accuracy numeric(5,4),
    hallucination_rate numeric(5,4),
    notes text,
    created_at timestamptz not null default now()
);

create table if not exists public.search_jobs (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid not null references auth.users(id) on delete cascade,
    query text not null,
    profile jsonb not null default '{}'::jsonb,
    status text not null default 'queued',
    progress_message text,
    result jsonb,
    error text,
    current_stage text,
    stage_payload jsonb not null default '{}'::jsonb,
    attempt_count integer not null default 0,
    cancelled_at timestamptz,
    created_at timestamptz not null default now(),
    started_at timestamptz,
    completed_at timestamptz,
    updated_at timestamptz not null default now()
);

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

create table if not exists public.search_cache (
    query text primary key,
    provider text not null,
    results jsonb not null default '[]'::jsonb,
    fetched_at timestamptz not null default now(),
    expires_at timestamptz not null
);

create table if not exists public.admin_users (
    user_id uuid primary key references auth.users(id) on delete cascade,
    created_at timestamptz not null default now()
);

create table if not exists public.user_opportunity_matches (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid not null references auth.users(id) on delete cascade,
    opportunity_id uuid not null references public.opportunities(id) on delete cascade,
    eligibility_result jsonb,
    priority text,
    priority_score numeric,
    notes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, opportunity_id)
);

create table if not exists public.reminder_deliveries (
    id uuid primary key default uuid_generate_v4(),
    task_id uuid not null references public.application_tasks(id) on delete cascade,
    reminder_date date not null,
    notification_email text not null,
    sent_at timestamptz not null default now(),
    provider_response jsonb,
    unique (task_id, reminder_date, notification_email)
);

create table if not exists public.opportunity_embeddings (
    opportunity_id uuid primary key references public.opportunities(id) on delete cascade,
    embedding vector(1024),
    created_at timestamptz not null default now()
);

create index if not exists opportunity_embeddings_embedding_idx
on public.opportunity_embeddings using ivfflat (embedding vector_cosine_ops) with (lists = 100);

alter table public.student_profiles enable row level security;
alter table public.opportunities enable row level security;
alter table public.opportunity_sources enable row level security;
alter table public.saved_opportunities enable row level security;
alter table public.application_tasks enable row level security;
alter table public.notification_preferences enable row level security;
alter table public.generated_documents enable row level security;
alter table public.uploaded_files enable row level security;
alter table public.source_pages enable row level security;
alter table public.eval_runs enable row level security;
alter table public.opportunity_embeddings enable row level security;
alter table public.search_jobs enable row level security;
alter table public.api_call_logs enable row level security;
alter table public.search_cache enable row level security;
alter table public.admin_users enable row level security;
alter table public.user_opportunity_matches enable row level security;
alter table public.reminder_deliveries enable row level security;

create or replace function public.is_admin_user(check_user_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select exists (select 1 from public.admin_users where user_id = check_user_id);
$$;

revoke all on function public.is_admin_user(uuid) from public;
grant execute on function public.is_admin_user(uuid) to authenticated;

create or replace function public.match_opportunities(query_embedding vector(1024), match_threshold float, match_count int)
returns table (opportunity_id uuid, similarity float)
language sql stable
as $$
    select opportunity_id, 1 - (embedding <=> query_embedding) as similarity
    from public.opportunity_embeddings
    where 1 - (embedding <=> query_embedding) > match_threshold
    order by embedding <=> query_embedding
    limit match_count;
$$;

create or replace function public.due_reminder_tasks()
returns table (
    user_id uuid,
    notification_email text,
    task_id uuid,
    title text,
    due_date date,
    status text
)
language sql stable
as $$
    select t.user_id, p.notification_email, t.id as task_id, t.title, t.due_date, t.status
    from public.application_tasks t
    join public.notification_preferences p on p.user_id = t.user_id
    where p.email_enabled = true
      and p.notification_email is not null
      and t.status = 'pending'
      and t.due_date is not null
      and (t.due_date - current_date) = any(p.reminder_days);
$$;

