"""Email delivery.

smtp mode: sends real email through SMTP_* settings (use this for any public deployment).
dev mode:  sends nothing and returns the text, so the page can show the link.
           Anyone can then verify any address, so dev mode is for local demos only.
"""
import smtplib
from email.message import EmailMessage

from app import config


def deliver(to: str, subject: str, text: str) -> str | None:
    if config.EMAIL_MODE == "smtp":
        msg = EmailMessage()
        msg["From"] = config.SMTP_FROM
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(text)
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as server:
            server.starttls()
            if config.SMTP_USER:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(msg)
        return None
    return text
