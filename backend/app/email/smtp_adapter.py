import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from loguru import logger

from app.config import settings
from app.email.interface import EmailService


class SMTPEmailService(EmailService):
    async def send_email(self, to: str, subject: str, body: str, html: str | None = None) -> None:
        message = MIMEMultipart("alternative")
        message["From"] = settings.smtp_from
        message["To"] = to
        message["Subject"] = subject

        message.attach(MIMEText(body, "plain"))
        if html:
            message.attach(MIMEText(html, "html"))

        try:
            await aiosmtplib.send(
                message,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user or None,
                password=settings.smtp_password or None,
                use_tls=settings.smtp_use_tls,
            )
            logger.info("email.sent", to=to, subject=subject)
        except Exception as e:
            logger.error("email.send_failed", to=to, subject=subject, error=str(e))
            raise


def get_email_service() -> EmailService:
    return SMTPEmailService()
