from flask import current_app, current_app, session
from datetime import datetime, timedelta, timezone
from app.models.user import User
from app.models.otp_log import OtpLog, BlockedIp

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

def verify_request(xuid: str, request_ip: str) -> None:
    """ Prevent spam and abuse by checking recent OTP logs for the user and IP address.
        Raises VerificationError if too many attempts or suspicious activity is detected.
    """

    if (block_ip := BlockedIp.query.filter_by(ip_address=request_ip).first()):
        raise SuspiciousActivity(block_ip.reason or "This IP address has been blocked due to suspicious activity.")

    # Recent logs for this user
    recent_logs = (
        OtpLog.query
        .filter_by(xuid=xuid)
        .order_by(OtpLog.timestamp.desc())
        .limit(10)
        .all()
    )

    if recent_logs and len(recent_logs) >= 5:
        raise TooManyAttempts()

    # Recent logs for this IP (to detect mass account creation)
    recent_ip_logs = (
        OtpLog.query
        .filter_by(ip_address=request_ip)
        .all()
    )

    distinct_xuids = set(log.xuid for log in recent_ip_logs)
    # If this IP has attempted to set up more than 3 different accounts, block
    if len(distinct_xuids) >= 3:
        blocked_ip = BlockedIp(ip_address=request_ip, reason=BlockedIp.REASON_TOO_MANY_ATTEMPTS)
        from app import db
        db.session.add(blocked_ip)
        db.session.commit()
        raise SuspiciousActivity("Suspicious activity detected from this IP address.")

def send_verification_pin(user: User, discord_id: int, request_ip: str) -> None:
    """Send the verification PIN to the user's linked Discord account via webhook."""

    # Raises VerificationError if there are too many attempts or suspicious activity detected
    # Handled by the caller to provide appropriate feedback to the user
    if request_ip:
        verify_request(user.xuid, request_ip)
    else:
        current_app.logger.warning(f"Verification attempt for user {user.username} without IP address.")

    session['pending_registration'] = {
        'xuid': user.xuid,
        'username': user.username,
        'password_hash': user.password_hash,
        'role': user.role.name
    }

    import secrets
    pin = f"{secrets.randbelow(1_000_000):06d}"
    if request_ip: OtpLog.log_attempt(user.xuid, pin, request_ip)

    msg = f"<@{discord_id}>, please use the following PIN to verify your account: `{pin}`"
    from app.utils.discord_webhook_utils import send, ChannelWebhookUrl
    # Raises WebhookError if sending fails, which should be handled by the caller to provide feedback to the user
    send(ChannelWebhookUrl.SECURE_WEBHOOK_URL, username="NetherGames PLX Registration", content=msg)
