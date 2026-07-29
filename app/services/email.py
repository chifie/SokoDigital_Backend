import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


def _build_html(template_name: str, context: dict[str, Any]) -> str:
    """Return a simple inline-HTML email body for the given template.

    Extend this function with proper template rendering (Jinja2, etc.)
    when needed.
    """
    if template_name == "welcome":
        name = context.get("name", "there")
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2>Welcome to SokoDigital, {name}! 🎉</h2>
            <p>Thank you for creating an account. You can now browse products,
            place orders, and enjoy a seamless shopping experience.</p>
            <p><a href="{context.get('app_url', '#')}"
                  style="background: #10b981; color: #fff; padding: 10px 20px;
                         text-decoration: none; border-radius: 6px;">
                Start Shopping</a></p>
            <hr>
            <p style="color: #999; font-size: 12px;">SokoDigital Marketplace</p>
        </body>
        </html>
        """

    if template_name == "order_confirmation":
        order_id = context.get("order_id", "N/A")
        items_html = ""
        for item in context.get("items", []):
            items_html += f"<li>{item.get('name', 'Item')} x{item.get('qty', 1)} — ${item.get('price', 0):.2f}</li>"
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2>Order Confirmed! ✅</h2>
            <p>Your order <strong>#{order_id[:8]}</strong> has been placed successfully.</p>
            <h3>Items:</h3>
            <ul>{items_html}</ul>
            <p><strong>Total:</strong> ${context.get('total', 0):.2f}</p>
            <p><a href="{context.get('tracking_url', '#')}"
                  style="background: #10b981; color: #fff; padding: 10px 20px;
                         text-decoration: none; border-radius: 6px;">
                Track Order</a></p>
            <hr>
            <p style="color: #999; font-size: 12px;">SokoDigital Marketplace</p>
        </body>
        </html>
        """

    if template_name == "email_verification":
        verify_url = context.get("verify_url", "#")
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2>Verify your email address ✅</h2>
            <p>Thanks for joining SokoDigital! Please verify your email by clicking the button below.</p>
            <p><a href="{verify_url}"
                  style="background: #10b981; color: #fff; padding: 12px 24px;
                         text-decoration: none; border-radius: 6px; display: inline-block;">
                Verify Email</a></p>
            <p>This link expires in 24 hours.</p>
            <p>If you didn't create an account, you can safely ignore this email.</p>
            <hr>
            <p style="color: #999; font-size: 12px;">SokoDigital Marketplace</p>
        </body>
        </html>
        """

    if template_name == "newsletter_welcome":
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2>You're subscribed! 📬</h2>
            <p>Thank you for subscribing to the SokoDigital newsletter. You'll
            receive updates on new products, flash sales, and exclusive offers.</p>
            <hr>
            <p style="color: #999; font-size: 12px;">
                SokoDigital Marketplace |
                <a href="{context.get('unsubscribe_url', '#')}">Unsubscribe</a>
            </p>
        </body>
        </html>
        """

    if template_name == "password_reset":
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2>Password Reset Request</h2>
            <p>Click the button below to reset your password. This link expires in 1 hour.</p>
            <p><a href="{context.get('reset_url', '#')}"
                  style="background: #f59e0b; color: #fff; padding: 10px 20px;
                         text-decoration: none; border-radius: 6px;">
                Reset Password</a></p>
            <p>If you didn't request this, you can safely ignore this email.</p>
            <hr>
            <p style="color: #999; font-size: 12px;">SokoDigital Marketplace</p>
        </body>
        </html>
        """

    # Fallback plain-text template
    return f"<p>{context.get('message', 'Hello from SokoDigital!')}</p>"


def _get_subject(template_name: str) -> str:
    subjects = {
        "welcome": "Welcome to SokoDigital! 🎉",
        "email_verification": "Verify your email — SokoDigital",
        "order_confirmation": "Order Confirmed ✅ — SokoDigital",
        "newsletter_welcome": "Thanks for subscribing! 📬",
        "password_reset": "Password Reset — SokoDigital",
    }
    return subjects.get(template_name, "Notification from SokoDigital")


def _send_sync(
    to_email: str,
    template_name: str,
    context: dict[str, Any],
) -> bool:
    """Synchronous SMTP send — runs in a thread to avoid blocking the event loop."""
    html = _build_html(template_name, context)
    subject = _get_subject(template_name)
    from_email = settings.SMTP_FROM_EMAIL or settings.SMTP_USER

    msg = MIMEMultipart("alternative")
    msg["From"] = f"SokoDigital <{from_email}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html, "html"))

    server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
    server.starttls()
    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
    server.sendmail(from_email, [to_email], msg.as_string())
    server.quit()
    logger.info("Email sent to %s (template=%s)", to_email, template_name)
    return True


async def send_email(
    to_email: str,
    template_name: str,
    context: dict[str, Any] | None = None,
) -> bool:
    """Send an email via SMTP in a background thread.

    Returns ``True`` on success, ``False`` if SMTP is not configured.
    Raises on other errors.
    """
    if not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("SMTP not configured — skipping email to %s", to_email)
        return False

    try:
        return await asyncio.to_thread(
            _send_sync, to_email, template_name, context or {}
        )
    except smtplib.SMTPException as exc:
        logger.error("Failed to send email to %s: %s", to_email, exc)
        raise
