"""Real SMTP transport; no console fallback and no import-time connection."""

from email.message import EmailMessage
import smtplib
import ssl

from backend.config import ConfigurationError


class EmailDeliveryError(Exception):
    """Safe delivery failure with no credentials, recipient, or message content."""


class SmtpSender:
    def __init__(self, settings, *, smtp_factory=None, smtp_ssl_factory=None):
        self.settings = settings
        # Explicit injection is for isolated protocol tests; runtime uses stdlib.
        self.smtp_factory = smtp_factory or smtplib.SMTP
        self.smtp_ssl_factory = smtp_ssl_factory or smtplib.SMTP_SSL

    def send_code(self, recipient, code, purpose):
        connection = None
        try:
            self.settings.validate_email_delivery()
            context = ssl.create_default_context()
            message = EmailMessage()
            purpose_text = {"registration": "university email verification", "password_reset": "password reset"}[purpose]
            message["Subject"] = f"Student Marketplace: {purpose_text}"
            message["From"] = self.settings.smtp_from_email
            message["To"] = recipient
            message.set_content(f"Your Student Marketplace {purpose_text} code is: {code}\n\nThis code is valid for ten minutes. If you did not request it, ignore this email.")
            if self.settings.smtp_security == "tls":
                connection = self.smtp_ssl_factory(self.settings.smtp_host, self.settings.smtp_port, timeout=10, context=context, local_hostname="student-marketplace.local")
            else:
                connection = self.smtp_factory(self.settings.smtp_host, self.settings.smtp_port, timeout=10, local_hostname="student-marketplace.local")
                connection.ehlo()
                connection.starttls(context=context)
                connection.ehlo()
            connection.login(self.settings.smtp_username.get_secret_value(), self.settings.smtp_password.get_secret_value())
            refused = connection.send_message(message)
            if refused:
                raise smtplib.SMTPRecipientsRefused(refused)
            connection.quit()
        except (ConfigurationError, smtplib.SMTPException, OSError, ssl.SSLError, UnicodeError):
            raise EmailDeliveryError("Verification email delivery is unavailable") from None
        finally:
            if connection is not None:
                connection.close()
