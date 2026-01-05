"""
Email service for sending verification emails, password resets, etc.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

import structlog

from app.core.config import settings

logger = structlog.get_logger()


class EmailService:
    """Email service for sending transactional emails."""

    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM

    async def send_email(
        self,
        to: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """
        Send an email.

        Args:
            to: Recipient email address
            subject: Email subject
            html_content: HTML email content
            text_content: Plain text email content (optional)

        Returns:
            True if sent successfully, False otherwise
        """
        # In development mode without SMTP credentials, log to console
        if not self.smtp_user or not self.smtp_password:
            logger.info(
                "email_dev_mode",
                to=to,
                subject=subject,
                content=text_content or html_content,
            )
            print("\n" + "="*80)
            print(f"📧 DEV EMAIL TO: {to}")
            print(f"📧 SUBJECT: {subject}")
            print("="*80)
            print(text_content or html_content)
            print("="*80 + "\n")
            return True

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["From"] = self.from_email
            msg["To"] = to
            msg["Subject"] = subject

            # Add text and HTML parts
            if text_content:
                msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info("email_sent", to=to, subject=subject)
            return True

        except Exception as e:
            logger.error("email_send_failed", to=to, subject=subject, error=str(e))
            return False

    async def send_verification_email(self, email: str, token: str) -> bool:
        """
        Send email verification email.

        Args:
            email: User email address
            token: Verification token

        Returns:
            True if sent successfully
        """
        verification_url = f"{settings.ALLOWED_ORIGINS[0]}/auth/verify-email?token={token}"

        subject = "Verify your email - Smart Stock Bot"

        text_content = f"""
Welcome to Smart Stock Bot!

Please verify your email address by clicking the link below:
{verification_url}

This link will expire in 24 hours.

If you didn't create an account, please ignore this email.
"""

        html_content = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #2563eb;">Welcome to Smart Stock Bot!</h2>
        <p>Thank you for signing up. Please verify your email address by clicking the button below:</p>
        <div style="margin: 30px 0;">
            <a href="{verification_url}"
               style="background-color: #2563eb; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">
                Verify Email
            </a>
        </div>
        <p>Or copy and paste this link into your browser:</p>
        <p style="color: #666; font-size: 14px; word-break: break-all;">{verification_url}</p>
        <p style="margin-top: 30px; font-size: 14px; color: #666;">
            This link will expire in 24 hours.<br>
            If you didn't create an account, please ignore this email.
        </p>
    </div>
</body>
</html>
"""

        return await self.send_email(email, subject, html_content, text_content)

    async def send_password_reset_email(self, email: str, token: str) -> bool:
        """
        Send password reset email.

        Args:
            email: User email address
            token: Password reset token

        Returns:
            True if sent successfully
        """
        reset_url = f"{settings.ALLOWED_ORIGINS[0]}/auth/reset-password?token={token}"

        subject = "Password Reset - Smart Stock Bot"

        text_content = f"""
Password Reset Request

We received a request to reset your password for Smart Stock Bot.

Click the link below to reset your password:
{reset_url}

This link will expire in 1 hour.

If you didn't request a password reset, please ignore this email or contact support if you have concerns.
"""

        html_content = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #2563eb;">Password Reset Request</h2>
        <p>We received a request to reset your password for Smart Stock Bot.</p>
        <div style="margin: 30px 0;">
            <a href="{reset_url}"
               style="background-color: #2563eb; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">
                Reset Password
            </a>
        </div>
        <p>Or copy and paste this link into your browser:</p>
        <p style="color: #666; font-size: 14px; word-break: break-all;">{reset_url}</p>
        <p style="margin-top: 30px; font-size: 14px; color: #666;">
            This link will expire in 1 hour.<br>
            If you didn't request a password reset, please ignore this email or contact support if you have concerns.
        </p>
    </div>
</body>
</html>
"""

        return await self.send_email(email, subject, html_content, text_content)

    async def send_mfa_enabled_email(self, email: str) -> bool:
        """Send notification that MFA was enabled."""
        subject = "MFA Enabled - Smart Stock Bot"

        text_content = """
Multi-Factor Authentication Enabled

Two-factor authentication has been successfully enabled for your Smart Stock Bot account.

Your account is now more secure!

If you didn't enable MFA, please contact support immediately.
"""

        html_content = """
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #16a34a;">Multi-Factor Authentication Enabled</h2>
        <p>Two-factor authentication has been successfully enabled for your Smart Stock Bot account.</p>
        <p>Your account is now more secure! 🔒</p>
        <p style="margin-top: 30px; font-size: 14px; color: #666;">
            If you didn't enable MFA, please contact support immediately.
        </p>
    </div>
</body>
</html>
"""

        return await self.send_email(email, subject, html_content, text_content)


# Global email service instance
email_service = EmailService()
