# Copyright Polymorph Corporation (2026)

"""Email notification system for extension requests."""

import os
import smtplib
from email.message import EmailMessage
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def send_extension_request_notification(
    request_id: str,
    session_id: str,
    email: str,
    admin_email: str,
    admin_url: str,
    smtp_config: dict
) -> bool:
    """Send email to Eric when extension request is created."""

    # Validate required config
    required_keys = ['host', 'port', 'from_email']
    if not all(key in smtp_config for key in required_keys):
        logger.error("Missing required SMTP configuration")
        return False

    if not admin_email:
        logger.error("ADMIN_EMAIL not configured")
        return False

    msg = EmailMessage()
    msg['Subject'] = f'ProfileGPT Extension Request from {email}'
    msg['From'] = smtp_config['from_email']
    msg['To'] = admin_email

    msg.set_content(f"""
New extension request received:

Email: {email}
Session ID: {session_id}
Request ID: {request_id}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Review and approve:
{admin_url}/extension-requests?key=YOUR_KEY

--
ProfileGPT Extension Request System
""")

    # Send via SMTP
    try:
        with smtplib.SMTP(smtp_config['host'], smtp_config['port'], timeout=10) as smtp:
            if smtp_config.get('use_tls'):
                smtp.starttls()
            if smtp_config.get('username') and smtp_config.get('password'):
                smtp.login(smtp_config['username'], smtp_config['password'])
            smtp.send_message(msg)

        logger.info(f"Extension request notification sent to {admin_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send extension request notification: {e}")
        return False
