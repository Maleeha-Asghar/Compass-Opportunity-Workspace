alter table public.generated_documents
    add column if not exists source_upload_id uuid references public.uploaded_files(id) on delete set null;

create index if not exists generated_documents_source_upload_idx
on public.generated_documents (source_upload_id);
