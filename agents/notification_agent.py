class NotificationAgent:
    def format_reminder(self, task: dict) -> str:
        title = task.get("title", "Application task")
        due_date = task.get("due_date", "soon")
        return f"Reminder: {title} is due on {due_date}."
