from app.config import Settings


def test_gmail_style_smtp_env_names_are_supported() -> None:
    settings = Settings(
        _env_file=None,
        EMAIL_HOST="smtp.gmail.com",
        EMAIL_PORT=587,
        EMAIL_USER="student@example.com",
        EMAIL_PASS="app-password",
        EMAIL_ENABLED=True,
    )

    assert settings.effective_email_provider == "smtp"
    assert settings.email_from == "student@example.com"
    assert settings.smtp_host == "smtp.gmail.com"
    assert settings.smtp_port == 587
    assert settings.smtp_username == "student@example.com"
    assert settings.smtp_password == "app-password"
    assert settings.smtp_uses_ssl is False
    assert settings.email_configured is True
