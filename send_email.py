import logging
import os
import smtplib
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

from dotenv import load_dotenv


load_dotenv()

logger = logging.getLogger(__name__)

PORT = int(os.getenv("SMTP_PORT", "587"))
EMAIL_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SENDER_NAME = os.getenv("SENDER_NAME", "Reminder Bot")
SENDER_EMAIL = os.getenv("EMAIL")
SENDER_PASSWORD = os.getenv("PASSWORD")


def is_valid_email(email: str) -> bool:
    _, parsed_email = parseaddr(email)
    return "@" in parsed_email and "." in parsed_email.rsplit("@", 1)[-1]


def validate_email_config() -> None:
    missing = []
    if not SENDER_EMAIL:
        missing.append("EMAIL")
    if not SENDER_PASSWORD:
        missing.append("PASSWORD")

    if missing:
        missing_as_text = ", ".join(missing)
        raise RuntimeError(
            f"Missing required environment variables for email sending: {missing_as_text}"
        )


def send_email(
    subject: str,
    recipient_email: str,
    name: str,
    due_date: str,
    invoice_no: str,
    amount: object,
) -> None:
    validate_email_config()

    recipient_email = recipient_email.strip()
    if not is_valid_email(recipient_email):
        raise ValueError(f"Invalid recipient email: {recipient_email}")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((SENDER_NAME, SENDER_EMAIL))
    msg["To"] = recipient_email
    msg["BCC"] = SENDER_EMAIL

    msg.set_content(
        (
            f"Hi {name},\n\n"
            "I hope you are well.\n"
            f"This is a reminder that {amount} USD for invoice {invoice_no} "
            f"is due on {due_date}.\n"
            "Please confirm that payment is on track.\n\n"
            "Best regards,\n"
            f"{SENDER_NAME}\n"
        )
    )

    msg.add_alternative(
        (
            "<html>"
            "<body>"
            f"<p>Hi {name},</p>"
            "<p>I hope you are well.</p>"
            f"<p>This is a reminder that <strong>{amount} USD</strong> for invoice "
            f"<strong>{invoice_no}</strong> is due on <strong>{due_date}</strong>.</p>"
            "<p>Please confirm that payment is on track.</p>"
            f"<p>Best regards,<br>{SENDER_NAME}</p>"
            "</body>"
            "</html>"
        ),
        subtype="html",
    )

    logger.info("Sending reminder email to %s", recipient_email)
    with smtplib.SMTP(EMAIL_SERVER, PORT, timeout=30) as server:
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
