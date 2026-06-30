from datetime import date

from agents.notification_agent import NotificationAgent
from tools.email_tool import EmailClient
from tools.supabase_tool import SupabaseRepository


def build_reminder_messages(tasks: list[dict]) -> list[str]:
    agent = NotificationAgent()
    return [agent.format_reminder(task) for task in tasks if task.get("status") == "pending"]


def send_due_reminders() -> list[dict]:
    repository = SupabaseRepository()
    email_client = EmailClient()
    agent = NotificationAgent()
    sent = []
    for task in repository.list_due_reminder_tasks():
        reminder_date = date.today().isoformat()
        if repository.has_reminder_delivery(task["task_id"], reminder_date, task["notification_email"]):
            continue
        message = agent.format_reminder(task)
        html_message = agent.format_reminder_html(task)
        response = email_client.send(
            to_email=task["notification_email"],
            subject="Compass application reminder",
            text=message,
            html=html_message,
        )
        repository.save_reminder_delivery(
            {
                "task_id": task["task_id"],
                "reminder_date": reminder_date,
                "notification_email": task["notification_email"],
                "provider_response": response,
            }
        )
        sent.append({"task_id": task["task_id"], "email_response": response})
    return sent


if __name__ == "__main__":
    send_due_reminders()
