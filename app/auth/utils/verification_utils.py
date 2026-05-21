from flask import current_app, session
from app.models.user import User
from app.models.otp_log import OtpLog

class VerificationError(Exception):
    """Custom exception for verification-related errors."""
    pass

class TooManyAttempts(VerificationError):
    """ Raised when a user has made too many verification attempts.
        Temporary blocking of user to be handled.
    """
    pass

class SuspiciousActivity(VerificationError):
    """Raised when suspicious activity is detected during verification."""
    pass

def verify_request(xuid: str) -> None:
    """Prevent spam and abuse by checking recent OTP logs for the user."""

    from datetime import datetime, timedelta, UTC

    recent_logs = (
        OtpLog.query
        .filter_by(xuid=xuid)
        .filter(OtpLog.timestamp >= datetime.now(UTC) - timedelta(minutes=30))
        .order_by(OtpLog.timestamp.desc())
        .limit(10)
        .all()
    )

    if recent_logs and len(recent_logs) >= 5:
        raise TooManyAttempts()

def send_verification_pin(user: User, discord_id: int) -> None:
    """Send the verification PIN to the user's linked Discord account via webhook."""

    # Raises VerificationError if there are too many attempts.
    # Handled by the caller to provide appropriate feedback to the user
    verify_request(user.xuid)

    session['pending_registration'] = {
        'xuid': user.xuid,
        'username': user.username,
        'password_hash': user.password_hash,
        'role': user.role.name
    }

    import secrets
    pin = f"{secrets.randbelow(1_000_000):06d}"
    OtpLog.log_attempt(user.xuid, pin)

    msg = f"<@{discord_id}>, please use the following PIN to verify your account: `{pin}`"
    from app.utils.discord_webhook_utils import send, ChannelWebhookUrl
    # Raises WebhookError if sending fails, which should be handled by the caller to provide feedback to the user
    send(ChannelWebhookUrl.SECURE_WEBHOOK_URL, username="NetherGames PLX Registration", content=msg)
