-- Store authoritative normalized opportunity types for UI grouping and filtering.

update public.opportunities
set opportunity_type = case
    when lower(coalesce(opportunity_type, '')) = 'internship'
        or lower(concat_ws(' ', opportunity_type, title, summary, funding_type)) like '%internship%'
        or lower(concat_ws(' ', opportunity_type, title, summary, funding_type)) like '%traineeship%'
        or lower(concat_ws(' ', opportunity_type, title, summary, funding_type)) like '%placement%'
        or lower(concat_ws(' ', opportunity_type, title, summary, funding_type)) like '%co-op%'
        then 'internship'
    when lower(coalesce(opportunity_type, '')) = 'masters'
        or lower(concat_ws(' ', opportunity_type, title, summary, funding_type)) like '%masters%'
        or lower(concat_ws(' ', opportunity_type, title, summary, funding_type)) like '%master''s%'
        or lower(concat_ws(' ', opportunity_type, title, summary, funding_type)) like '%master of%'
        or lower(concat_ws(' ', opportunity_type, title, summary, funding_type)) like '%msc%'
        or lower(concat_ws(' ', opportunity_type, title, summary, funding_type)) like '%m.sc%'
        or lower(concat_ws(' ', opportunity_type, title, summary, funding_type)) like '%ms program%'
        or lower(concat_ws(' ', opportunity_type, title, summary, funding_type)) like '%graduate degree%'
        or lower(concat_ws(' ', opportunity_type, title, summary, funding_type)) like '%postgraduate%'
        then 'masters'
    when lower(concat_ws(' ', opportunity_type, title, summary, funding_type)) like '%assistantship%'
        then 'assistantship'
    when lower(concat_ws(' ', opportunity_type, title, summary, funding_type)) like '%fellowship%'
        then 'fellowship'
    when lower(concat_ws(' ', opportunity_type, title, summary, funding_type)) like '%scholarship%'
        then 'scholarship'
    when lower(concat_ws(' ', opportunity_type, title, summary, funding_type)) like '%research program%'
        or lower(concat_ws(' ', opportunity_type, title, summary, funding_type)) like '%summer research%'
        or lower(concat_ws(' ', opportunity_type, title, summary, funding_type)) like '%research opportunity%'
        then 'research'
    else 'other'
end;

alter table public.opportunities
    alter column opportunity_type set default 'other',
    alter column opportunity_type set not null;

alter table public.opportunities
    drop constraint if exists opportunities_opportunity_type_check;

alter table public.opportunities
    add constraint opportunities_opportunity_type_check
    check (
        opportunity_type in (
            'masters',
            'internship',
            'scholarship',
            'fellowship',
            'assistantship',
            'research',
            'other'
        )
    );
