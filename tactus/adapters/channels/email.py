"""
Email notification channel for HITL interactions.

Sends email notifications for HITL requests. This is fire-and-forget -
no interactive responses via email.

Requirements:
    pip install aiosmtplib

Configuration:
    notifications:
      channels:
        email:
          enabled: true
          smtp_host: "smtp.example.com"
          smtp_port: 587
          smtp_username: ${SMTP_USERNAME}
          smtp_password: ${SMTP_PASSWORD}
          from_address: "tactus@example.com"
          recipients:
            - "ops@example.com"
            - "alerts@example.com"
          use_tls: true
"""

import logging
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Dict, Any, List

from tactus.protocols.models import HITLRequest
from tactus.protocols.notification import (
    ChannelCapabilities,
    NotificationDeliveryResult,
)

logger = logging.getLogger(__name__)

try:
    import aiosmtplib

    AIOSMTPLIB_AVAILABLE = True
except ImportError:
    AIOSMTPLIB_AVAILABLE = False
    aiosmtplib = None


class EmailNotificationChannel:
    """
    Email notification channel using SMTP.

    Sends HTML email notifications for HITL requests. Best suited for
    escalation alerts where you want to notify people who may not be
    monitoring other channels.

    Note: Email is fire-and-forget. Recipients should use their Tactus
    interface or API to respond.
    """

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int = 587,
        smtp_username: Optional[str] = None,
        smtp_password: Optional[str] = None,
        from_address: str = "tactus@localhost",
        recipients: Optional[List[str]] = None,
        use_tls: bool = True,
        enabled: bool = True,
        **kwargs: Any,
    ):
        """
        Initialize email notification channel.

        Args:
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port (587 for TLS, 465 for SSL, 25 for plain)
            smtp_username: SMTP authentication username
            smtp_password: SMTP authentication password
            from_address: Sender email address
            recipients: Default recipient email addresses
            use_tls: Whether to use STARTTLS
            enabled: Whether this channel is enabled
            **kwargs: Additional configuration (ignored)
        """
        if not AIOSMTPLIB_AVAILABLE:
            raise ImportError(
                "aiosmtplib is required for email notifications. "
                "Install with: pip install tactus[email]"
            )

        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.from_address = from_address
        self.recipients = recipients or []
        self.use_tls = use_tls
        self._enabled = enabled

        logger.info(
            f"EmailNotificationChannel initialized: {smtp_host}:{smtp_port}, "
            f"{len(self.recipients)} recipients"
        )

    @property
    def channel_id(self) -> str:
        """Return channel identifier."""
        return "email"

    @property
    def capabilities(self) -> ChannelCapabilities:
        """Return channel capabilities."""
        return ChannelCapabilities(
            supports_approval=False,  # Can't respond via email
            supports_input=False,
            supports_review=False,
            supports_escalation=True,  # Great for escalation alerts
            supports_interactive_buttons=False,
            supports_file_attachments=True,
            max_message_length=None,  # No practical limit
        )

    async def send_notification(
        self,
        procedure_id: str,
        request_id: str,
        request: HITLRequest,
        callback_url: str,
    ) -> NotificationDeliveryResult:
        """
        Send HITL notification via email.

        Args:
            procedure_id: Unique procedure identifier
            request_id: Unique request identifier
            request: HITLRequest with interaction details
            callback_url: URL for response callbacks (for info only)

        Returns:
            NotificationDeliveryResult with delivery status
        """
        if not self.recipients:
            return NotificationDeliveryResult(
                channel_id=self.channel_id,
                external_message_id="",
                delivered_at=datetime.now(timezone.utc),
                success=False,
                error_message="No email recipients configured",
            )

        try:
            # Build email
            message = self._build_email(procedure_id, request_id, request)

            # Send via SMTP
            await aiosmtplib.send(
                message,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_username,
                password=self.smtp_password,
                start_tls=self.use_tls,
            )

            # Generate message ID
            message_id = f"email_{request_id}_{int(datetime.now().timestamp())}"

            logger.info(
                f"Sent email notification for {request_id} to "
                f"{len(self.recipients)} recipients"
            )

            return NotificationDeliveryResult(
                channel_id=self.channel_id,
                external_message_id=message_id,
                delivered_at=datetime.now(timezone.utc),
                success=True,
            )

        except Exception as e:
            logger.exception(f"Failed to send email notification for {request_id}")
            return NotificationDeliveryResult(
                channel_id=self.channel_id,
                external_message_id="",
                delivered_at=datetime.now(timezone.utc),
                success=False,
                error_message=str(e),
            )

    async def cancel_notification(
        self,
        external_message_id: str,
        reason: str = "Resolved via another channel",
    ) -> None:
        """
        Cancel notification (sends follow-up email).

        Unlike other channels, we can send a follow-up email to notify
        recipients that the request was resolved.
        """
        # Optionally send a follow-up email
        # For now, this is a no-op to avoid email spam
        logger.debug(
            f"Email notification {external_message_id} resolved: {reason}. "
            f"No follow-up email sent."
        )

    def _build_email(
        self, procedure_id: str, request_id: str, request: HITLRequest
    ) -> MIMEMultipart:
        """
        Build email message.

        Args:
            procedure_id: Unique procedure identifier
            request_id: Unique request identifier
            request: HITLRequest with interaction details

        Returns:
            MIMEMultipart email message
        """
        message = MIMEMultipart("alternative")

        # Headers
        message["Subject"] = self._build_subject(request)
        message["From"] = self.from_address
        message["To"] = ", ".join(self.recipients)

        # Plain text version
        text_body = self._build_text_body(procedure_id, request_id, request)
        message.attach(MIMEText(text_body, "plain"))

        # HTML version
        html_body = self._build_html_body(procedure_id, request_id, request)
        message.attach(MIMEText(html_body, "html"))

        return message

    def _build_subject(self, request: HITLRequest) -> str:
        """Build email subject line."""
        emoji = self._get_emoji(request.request_type)
        return f"[Tactus] {emoji} {request.request_type.title()} Required"

    def _build_text_body(
        self, procedure_id: str, request_id: str, request: HITLRequest
    ) -> str:
        """Build plain text email body."""
        lines = [
            f"{request.request_type.upper()} REQUIRED",
            "=" * 40,
            "",
            request.message,
            "",
            f"Procedure: {procedure_id}",
            f"Request ID: {request_id}",
            f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
        ]

        if request.options:
            lines.append("Options:")
            for i, opt in enumerate(request.options):
                label = opt.get("label", f"Option {i + 1}")
                lines.append(f"  {i + 1}. {label}")
            lines.append("")

        lines.extend(
            [
                "Please respond via your Tactus interface or API.",
                "",
                "---",
                "This is an automated message from Tactus.",
            ]
        )

        return "\n".join(lines)

    def _build_html_body(
        self, procedure_id: str, request_id: str, request: HITLRequest
    ) -> str:
        """Build HTML email body."""
        color = self._get_color(request.request_type)
        emoji = self._get_emoji(request.request_type)

        options_html = ""
        if request.options:
            items = "".join(
                f"<li>{opt.get('label', f'Option {i+1}')}</li>"
                for i, opt in enumerate(request.options)
            )
            options_html = f"""
            <div style="margin: 16px 0;">
                <strong>Options:</strong>
                <ul style="margin: 8px 0;">{items}</ul>
            </div>
            """

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    line-height: 1.5;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background-color: {color};
                    color: white;
                    padding: 16px;
                    border-radius: 8px 8px 0 0;
                    font-size: 18px;
                    font-weight: bold;
                }}
                .content {{
                    border: 1px solid #ddd;
                    border-top: none;
                    padding: 20px;
                    border-radius: 0 0 8px 8px;
                }}
                .message {{
                    font-size: 16px;
                    margin-bottom: 20px;
                    white-space: pre-wrap;
                }}
                .metadata {{
                    background-color: #f5f5f5;
                    padding: 12px;
                    border-radius: 4px;
                    font-size: 14px;
                }}
                .metadata-item {{
                    margin: 4px 0;
                }}
                .footer {{
                    margin-top: 20px;
                    padding-top: 16px;
                    border-top: 1px solid #ddd;
                    font-size: 12px;
                    color: #666;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                {emoji} {request.request_type.upper()} REQUIRED
            </div>
            <div class="content">
                <div class="message">{request.message}</div>
                {options_html}
                <div class="metadata">
                    <div class="metadata-item"><strong>Procedure:</strong> {procedure_id}</div>
                    <div class="metadata-item"><strong>Request ID:</strong> {request_id}</div>
                    <div class="metadata-item"><strong>Time:</strong> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
                </div>
                <div class="footer">
                    <p>Please respond via your Tactus interface or API.</p>
                    <p>This is an automated message from Tactus.</p>
                </div>
            </div>
        </body>
        </html>
        """

    def _get_color(self, request_type: str) -> str:
        """Get header color for request type."""
        colors = {
            "approval": "#f0ad4e",  # Orange
            "input": "#5bc0de",  # Blue
            "review": "#9b59b6",  # Purple
            "escalation": "#d9534f",  # Red
        }
        return colors.get(request_type.lower(), "#777")

    def _get_emoji(self, request_type: str) -> str:
        """Get emoji for request type."""
        return {
            "approval": "❓",
            "input": "✏️",
            "review": "🔍",
            "escalation": "🚨",
        }.get(request_type.lower(), "🔔")
