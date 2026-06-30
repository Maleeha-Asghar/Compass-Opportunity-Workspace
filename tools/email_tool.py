import requests
import smtplib
from email.message import EmailMessage

from app.config import Settings, get_settings


class EmailClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def send(self, to_email: str, subject: str, text: str, html: str | None = None) -> dict:
        api_key, from_email = self.settings.require_email()
        provider = self.settings.effective_email_provider
        if provider == "smtp":
            return self._send_smtp(from_email, to_email, subject, text, html)
        if provider == "postmark":
            return self._send_postmark(api_key, from_email, to_email, subject, text, html)
        return self._send_resend(api_key, from_email, to_email, subject, text, html)

    def _send_smtp(self, from_email: str, to_email: str, subject: str, text: str, html: str | None = None) -> dict:
        message = EmailMessage()
        message["From"] = from_email
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(text)
        if html:
            message.add_alternative(html, subtype="html")

        if self.settings.smtp_uses_ssl:
            with smtplib.SMTP_SSL(self.settings.smtp_host, self.settings.smtp_port, timeout=30) as smtp:
                smtp.login(self.settings.smtp_username, self.settings.smtp_password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=30) as smtp:
                smtp.starttls()
                smtp.login(self.settings.smtp_username, self.settings.smtp_password)
                smtp.send_message(message)
        return {"provider": "smtp", "to": to_email, "sent": True}

    @staticmethod
    def _send_resend(
        api_key: str,
        from_email: str,
        to_email: str,
        subject: str,
        text: str,
        html: str | None = None,
    ) -> dict:
        payload = {"from": from_email, "to": [to_email], "subject": subject, "text": text}
        if html:
            payload["html"] = html
        response = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _send_postmark(
        api_key: str,
        from_email: str,
        to_email: str,
        subject: str,
        text: str,
        html: str | None = None,
    ) -> dict:
        payload = {"From": from_email, "To": to_email, "Subject": subject, "TextBody": text}
        if html:
            payload["HtmlBody"] = html
        response = requests.post(
            "https://api.postmarkapp.com/email",
            headers={"X-Postmark-Server-Token": api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
