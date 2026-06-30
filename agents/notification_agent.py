from datetime import date
from html import escape
from pathlib import Path
from string import Template


class NotificationAgent:
    TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "compass_email_template_project_logo.html"

    def format_reminder(self, task: dict) -> str:
        opportunity_name = self._opportunity_name(task)
        opportunity_id = self._display_value(task.get("opportunity_id"), "Not assigned")
        status = self._display_value(task.get("status"), "pending").title()
        final_deadline = self._display_value(self._final_deadline(task), "Not specified")
        task_name = self._display_value(task.get("title"), "Application task")
        due_date = self._display_value(task.get("due_date"), "soon")
        return (
            f"Compass application reminder\n\n"
            f"Opportunity ID: {opportunity_id}\n"
            f"Opportunity name: {opportunity_name}\n"
            f"Application status: {status}\n"
            f"Final deadline: {final_deadline}\n"
            f"Current task: {task_name}\n"
            f"Task due date: {due_date}\n\n"
            "This email was generated automatically by Compass. Do not reply to this email."
        )

    def format_reminder_html(self, task: dict) -> str:
        template = Template(self.TEMPLATE_PATH.read_text(encoding="utf-8"))
        values = self._template_values(task)
        return template.safe_substitute({key: escape(value) for key, value in values.items()})

    def _template_values(self, task: dict) -> dict[str, str]:
        opportunity = task.get("opportunity") or {}
        final_deadline = self._final_deadline(task)
        task_due_date = task.get("due_date")
        provider_bits = [
            self._display_value(opportunity.get("provider"), ""),
            self._display_value(opportunity.get("country"), ""),
            self._display_value(opportunity.get("funding_type"), ""),
        ]
        provider_line = " | ".join(bit for bit in provider_bits if bit) or "Details available in Compass"
        application_url = self._display_value(opportunity.get("application_url"), "#")
        return {
            "student_name": self._display_value(task.get("student_name"), "there"),
            "opportunity_id": self._display_value(task.get("opportunity_id"), "Not assigned"),
            "opportunity_name": self._opportunity_name(task),
            "application_status": self._display_value(task.get("status"), "pending").title(),
            "final_deadline": self._display_value(final_deadline, "Not specified"),
            "task_name": self._display_value(task.get("title"), "Application task"),
            "task_due_date": self._display_value(task_due_date, "Soon"),
            "provider_line": provider_line,
            "next_action": self._next_action(task),
            "application_url": application_url,
            "generated_date": date.today().isoformat(),
        }

    @staticmethod
    def _display_value(value: object, fallback: str) -> str:
        if value is None or value == "":
            return fallback
        return str(value)

    def _opportunity_name(self, task: dict) -> str:
        opportunity = task.get("opportunity") or {}
        return self._display_value(opportunity.get("title") or task.get("opportunity_name"), "Tracked opportunity")

    @staticmethod
    def _final_deadline(task: dict) -> object:
        opportunity = task.get("opportunity") or {}
        return task.get("final_deadline") or opportunity.get("deadline") or task.get("due_date")

    def _next_action(self, task: dict) -> str:
        title = self._display_value(task.get("title"), "Review your application task")
        due_date = self._display_value(task.get("due_date"), "the reminder date")
        return f"Complete '{title}' by {due_date}, then update the application status in Compass."
