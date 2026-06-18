alter table if exists public.opportunity_embeddings
    drop constraint if exists opportunity_embeddings_opportunity_id_fkey;
alter table if exists public.opportunity_embeddings
    drop constraint if exists opportunity_embeddings_pkey;
alter table if exists public.opportunity_sources
    drop constraint if exists opportunity_sources_opportunity_id_fkey;
alter table if exists public.saved_opportunities
    drop constraint if exists saved_opportunities_opportunity_id_fkey;
alter table if exists public.application_tasks
    drop constraint if exists application_tasks_opportunity_id_fkey;
alter table if exists public.generated_documents
    drop constraint if exists generated_documents_opportunity_id_fkey;
alter table if exists public.user_opportunity_matches
    drop constraint if exists user_opportunity_matches_opportunity_id_fkey;
alter table if exists public.opportunities
    drop constraint if exists opportunities_pkey;

alter table public.opportunities
    add column if not exists uuid_id uuid default uuid_generate_v4();

update public.opportunities
set uuid_id = coalesce(uuid_id, uuid_generate_v4());

alter table public.opportunities
    add column if not exists public_code varchar(8);

update public.opportunities
set public_code = coalesce(public_code, id::text);

alter table public.opportunities
    alter column uuid_id set not null,
    alter column public_code set not null;

create unique index if not exists opportunities_public_code_key
on public.opportunities (public_code);

alter table public.opportunity_sources add column if not exists opportunity_uuid uuid;
update public.opportunity_sources s
set opportunity_uuid = o.uuid_id
from public.opportunities o
where s.opportunity_id::text = o.public_code
  and s.opportunity_uuid is null;

alter table public.saved_opportunities add column if not exists opportunity_uuid uuid;
update public.saved_opportunities s
set opportunity_uuid = o.uuid_id
from public.opportunities o
where s.opportunity_id::text = o.public_code
  and s.opportunity_uuid is null;

alter table public.application_tasks add column if not exists opportunity_uuid uuid;
update public.application_tasks t
set opportunity_uuid = o.uuid_id
from public.opportunities o
where t.opportunity_id::text = o.public_code
  and t.opportunity_uuid is null;

alter table public.generated_documents add column if not exists opportunity_uuid uuid;
update public.generated_documents d
set opportunity_uuid = o.uuid_id
from public.opportunities o
where d.opportunity_id::text = o.public_code
  and d.opportunity_uuid is null;

alter table public.user_opportunity_matches add column if not exists opportunity_uuid uuid;
update public.user_opportunity_matches m
set opportunity_uuid = o.uuid_id
from public.opportunities o
where m.opportunity_id::text = o.public_code
  and m.opportunity_uuid is null;

do $$
begin
    if exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'opportunity_embeddings'
          and column_name = 'opportunity_id'
    ) then
        execute 'alter table public.opportunity_embeddings add column if not exists opportunity_uuid uuid';
        execute '
            update public.opportunity_embeddings e
            set opportunity_uuid = o.uuid_id
            from public.opportunities o
            where e.opportunity_id::text = o.public_code
              and e.opportunity_uuid is null
        ';
        execute 'alter table public.opportunity_embeddings drop column opportunity_id';
        execute 'alter table public.opportunity_embeddings rename column opportunity_uuid to opportunity_id';
        execute 'alter table public.opportunity_embeddings alter column opportunity_id set not null';
    end if;
end $$;

alter table public.opportunity_sources drop column opportunity_id;
alter table public.opportunity_sources rename column opportunity_uuid to opportunity_id;
alter table public.opportunity_sources alter column opportunity_id set not null;

alter table public.saved_opportunities drop column opportunity_id;
alter table public.saved_opportunities rename column opportunity_uuid to opportunity_id;
alter table public.saved_opportunities alter column opportunity_id set not null;

alter table public.application_tasks drop column opportunity_id;
alter table public.application_tasks rename column opportunity_uuid to opportunity_id;

alter table public.generated_documents drop column opportunity_id;
alter table public.generated_documents rename column opportunity_uuid to opportunity_id;

alter table public.user_opportunity_matches drop column opportunity_id;
alter table public.user_opportunity_matches rename column opportunity_uuid to opportunity_id;
alter table public.user_opportunity_matches alter column opportunity_id set not null;

alter table public.opportunities drop column id;
alter table public.opportunities rename column uuid_id to id;
alter table public.opportunities add constraint opportunities_pkey primary key (id);

alter table public.opportunity_sources
    add constraint opportunity_sources_opportunity_id_fkey
    foreign key (opportunity_id) references public.opportunities(id) on delete cascade;

alter table public.opportunity_sources
    drop constraint if exists opportunity_sources_opportunity_id_url_key;
alter table public.opportunity_sources
    add constraint opportunity_sources_opportunity_id_url_key unique (opportunity_id, url);

alter table public.saved_opportunities
    add constraint saved_opportunities_opportunity_id_fkey
    foreign key (opportunity_id) references public.opportunities(id) on delete cascade;

alter table public.saved_opportunities
    drop constraint if exists saved_opportunities_user_id_opportunity_id_key;
alter table public.saved_opportunities
    add constraint saved_opportunities_user_id_opportunity_id_key unique (user_id, opportunity_id);

alter table public.application_tasks
    add constraint application_tasks_opportunity_id_fkey
    foreign key (opportunity_id) references public.opportunities(id) on delete cascade;

alter table public.generated_documents
    add constraint generated_documents_opportunity_id_fkey
    foreign key (opportunity_id) references public.opportunities(id) on delete set null;

alter table public.user_opportunity_matches
    add constraint user_opportunity_matches_opportunity_id_fkey
    foreign key (opportunity_id) references public.opportunities(id) on delete cascade;

alter table public.user_opportunity_matches
    drop constraint if exists user_opportunity_matches_user_id_opportunity_id_key;
alter table public.user_opportunity_matches
    add constraint user_opportunity_matches_user_id_opportunity_id_key unique (user_id, opportunity_id);

do $$
begin
    if exists (
        select 1
        from information_schema.tables
        where table_schema = 'public'
          and table_name = 'opportunity_embeddings'
    ) then
        execute 'alter table public.opportunity_embeddings add constraint opportunity_embeddings_pkey primary key (opportunity_id)';
        execute '
            alter table public.opportunity_embeddings
            add constraint opportunity_embeddings_opportunity_id_fkey
            foreign key (opportunity_id) references public.opportunities(id) on delete cascade
        ';
    end if;
end $$;

alter table public.opportunities
    drop column if exists eligibility_result,
    drop column if exists priority,
    drop column if exists priority_score;

create or replace function public.match_opportunities(
    query_embedding vector(1024),
    match_threshold float,
    match_count int
)
returns table (
    opportunity_id uuid,
    similarity float
)
language sql stable
as $$
    select
        opportunity_id,
        1 - (embedding <=> query_embedding) as similarity
    from public.opportunity_embeddings
    where 1 - (embedding <=> query_embedding) > match_threshold
    order by embedding <=> query_embedding
    limit match_count;
$$;
