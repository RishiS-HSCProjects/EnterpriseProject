from datetime import datetime, timedelta, timezone
from bcrypt import gensalt, hashpw, checkpw

from app import db

class OtpLog(db.Model):
    """Model to log OTP generation and verification attempts."""
    __tablename__ = 'otp_logs'

    id = db.Column(db.Integer, primary_key=True)
    xuid = db.Column(db.String(80), nullable=False)
    hashed_otp_code = db.Column(db.String(6), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=db.func.now())
    ip_address = db.Column(db.String(45), nullable=True)

    @staticmethod
    def log_attempt(xuid: str, otp_code: str, ip_address: str) -> None:

        hashed_code = hashpw(otp_code.encode(), gensalt()).decode('utf-8')

        otp_log = OtpLog(xuid=xuid, hashed_otp_code=hashed_code, ip_address=ip_address) # type: ignore
        db.session.add(otp_log)
        db.session.commit()

    @staticmethod
    def verify_otp(xuid: str, otp_code: str, ip_address: str) -> bool:
        """Verify the provided OTP code for the given XUID. Raises OtpLogError with specific messages for different failure cases."""
        recent_logs = (
            OtpLog.query
            .filter_by(xuid=xuid)
            .order_by(OtpLog.timestamp.desc())
            .limit(10)
            .all()
        )

        if not recent_logs:
            raise OtpLogNotFound("Failed to locate OTP log.")

        now = datetime.now(timezone.utc)

        valid_log = None
        for log in recent_logs:
            log_time = log.timestamp.replace(tzinfo=timezone.utc)
            if log_time + timedelta(minutes=30) > now:
                valid_log = log
                break
        if not valid_log:
            raise OtpLogExpired("OTP code has expired.")

        if valid_log.ip_address != ip_address:
            raise OtpLogInvalidIp("IP address does not match.")

        return hashpw(otp_code.encode(), valid_log.hashed_otp_code.encode()) == valid_log.hashed_otp_code.encode()

    def __repr__(self):
        return f"<OtpLog xuid={self.xuid} timestamp={self.timestamp} ip_address={self.ip_address}>"

class OtpLogError(Exception):
    """Base exception for OTP log errors."""
    pass

class OtpLogNotFound(OtpLogError):
    """Raised when no OTP log is found for a given XUID."""
    pass

class OtpLogExpired(OtpLogError):
    """Raised when an OTP code has expired."""
    pass

class OtpLogInvalidIp(OtpLogError):
    """Raised when the IP address does not match the OTP log."""
    pass

class BlockedIp(db.Model):
    """Model to log blocked IP addresses due to suspicious activity."""
    __tablename__ = 'blocked_ips'

    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), unique=True, nullable=False)
    blocked_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    reason = db.Column(db.String(255), nullable=True)

    REASON_TOO_MANY_ATTEMPTS = "User attempted verification of too many accounts from this IP."

    def __repr__(self):
        return f"<BlockedIp ip_address={self.ip_address} blocked_at={self.blocked_at} reason={self.reason}>"