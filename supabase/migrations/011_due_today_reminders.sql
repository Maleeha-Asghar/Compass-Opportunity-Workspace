alter table public.notification_preferences
    alter column reminder_days set default '{15,7,3,1,0}';

update public.notification_preferences
set reminder_days = array_append(reminder_days, 0)
where email_enabled = true
  and not (0 = any(reminder_days));
