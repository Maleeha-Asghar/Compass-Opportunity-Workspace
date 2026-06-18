alter table public.generated_documents
    add column if not exists parent_document_id uuid references public.generated_documents(id) on delete set null,
    add column if not exists version_number integer not null default 1,
    add column if not exists regeneration_instruction text,
    add column if not exists updated_at timestamptz not null default now();

create index if not exists generated_documents_parent_idx
on public.generated_documents (parent_document_id, version_number desc);
