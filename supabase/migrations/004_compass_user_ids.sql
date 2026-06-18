alter table public.student_profiles
    add column if not exists compass_user_id text;

create unique index if not exists student_profiles_compass_user_id_idx
    on public.student_profiles (compass_user_id)
    where compass_user_id is not null;

with numbered as (
    select
        user_id,
        format('cu_%s', row_number() over (order by created_at, user_id)) as compass_user_id
    from public.student_profiles
    where compass_user_id is null
)
update public.student_profiles as profiles
set compass_user_id = numbered.compass_user_id
from numbered
where profiles.user_id = numbered.user_id;
