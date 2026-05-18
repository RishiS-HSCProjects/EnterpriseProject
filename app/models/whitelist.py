from flask import current_app
from flask_login import current_user
from app import db

class Whitelist(db.Model):
    """User model for staff, managers, and admins."""
    __tablename__ = 'whitelist'

    id = db.Column(db.Integer, primary_key=True)
    xuid = db.Column(db.String(50), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    whitelisted_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    whitelisted_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    def unwhitelist(self):
        """Remove this user from the whitelist. Also deletes the associated User account if it exists."""
        from app.models.user import User
        if self.xuid:
            for user in User.query.filter_by(xuid=self.xuid).all():
                if user: user.delete()

        db.session.delete(self)

    def get_user(self):
        """Get the User associated with this whitelist entry, or None if not assigned."""
        from app.models.user import User
        if self.xuid:
            return User.query.filter_by(xuid=self.xuid).first()
        else:
            current_app.logger.warning(f"Whitelist entry for {self.username} has no associated User account.")
        return None

    @classmethod
    def whitelist_user(cls, username: str) -> "Whitelist":
        from app.models.user import User

        username = username.strip()
        excepted, data = User.validate_user(username)

        if not excepted:
            raise PermissionDenied(data)

        xuid = data.get('xuid')
        if not xuid:
            from app.models.user import UserNotFound
            raise UserNotFound(f"User {username} not found in NetherGames API.")

        username = data.get('name') # Handle for casing

        existing: Whitelist | None = cls.query.filter_by(xuid=xuid).first()
        if existing:
            raise UserAlreadyWhitelisted(username)

        whitelist_entry = cls()
        whitelist_entry.xuid = xuid
        whitelist_entry.username = username
        whitelist_entry.whitelisted_by = current_user.id
        return whitelist_entry

class WhitelistError(Exception):
    """Base exception for whitelist errors."""
    pass

class UserAlreadyWhitelisted(WhitelistError):
    """Raised when a user is already whitelisted."""
    def __init__(self, username):
        super().__init__(f"User {username} is already whitelisted.")

class UserNotWhitelisted(WhitelistError):
    """Raised when a user is not whitelisted."""
    pass

class PermissionDenied(WhitelistError):
    """Raised when a user does not have permission to be whitelisted."""
    pass
