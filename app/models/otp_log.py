from datetime import datetime, timedelta, timezone
from bcrypt import gensalt, hashpw, checkpw

from app import db

class OtpLog(db.Model):
    """Model to log OTP generation and verification attempts."""
    __tablename__ = 'otp_logs'

    id = db.Column(db.Integer, primary_key=True)
    xuid = db.Column(db.String(80), nullable=False)
    hashed_otp_code = db.Column(db.String(128), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=db.func.now())

    @staticmethod
    def log_attempt(xuid: str, otp_code: str) -> None:
        hashed_code = hashpw(otp_code.encode(), gensalt()).decode('utf-8')
        otp_log = OtpLog(xuid=xuid, hashed_otp_code=hashed_code) # type: ignore
        db.session.add(otp_log)
        db.session.commit()

    @staticmethod
    def verify_otp(xuid: str, otp_code: str) -> bool:
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

        return hashpw(otp_code.encode(), valid_log.hashed_otp_code.encode()) == valid_log.hashed_otp_code.encode()

    def __repr__(self):
        return f"<OtpLog xuid={self.xuid} timestamp={self.timestamp}>"

class OtpLogError(Exception):
    """Base exception for OTP log errors."""
    pass

class OtpLogNotFound(OtpLogError):
    """Raised when no OTP log is found for a given XUID."""
    pass

class OtpLogExpired(OtpLogError):
    """Raised when an OTP code has expired."""
    pass
