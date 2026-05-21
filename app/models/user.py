from flask import current_app
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from app.models.tournament import Tournament
from app.models.whitelist import UserNotWhitelisted, Whitelist
from ..utils.api_utils import request, NetherGamesAPIError, UnknownPlayer, MissingAccess, MaintenanceMode
from enum import Enum

class UserRole(Enum):
    STAFF = 0
    MANAGER = 1
    ADMIN = 2

    def __str__(self):
        return self.name.capitalize()

class User(UserMixin, db.Model):
    """User model for staff, managers, and admins."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    xuid = db.Column(db.String(50), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    _role = db.Column(db.String(20), nullable=False, default=UserRole.STAFF.name)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    last_login_at = db.Column(db.DateTime, nullable=True)

    def login(self):
        """Update last login time."""
        wl = Whitelist.query.filter_by(xuid=self.xuid).first()
        if wl:
            self.last_login_at = db.func.now()
            db.session.commit()
            from flask_login import login_user
            login_user(self)
        else:
            raise UserNotWhitelisted(f"User {self.username} is not whitelisted.")

    def delete(self):
        xuid = self.xuid

        # Query related objects with no autoflush
        # This prevents SQLAlchemy from trying to flush the session
        # (and thus commit the transaction) before we've finished making changes to related objects.
        with db.session.no_autoflush:
            tournaments = Tournament.query.filter_by(created_by=self.id).all()
            whitelist_entries = Whitelist.query.filter_by(whitelisted_by=self.id).all()

        for tournament in tournaments:
            tournament.set_created_by(xuid=xuid, delete_user=True)

        for wl in whitelist_entries:
            wl.whitelisted_by = None
            wl.whitelisted_by_xuid = xuid

        db.session.delete(self)

    @property
    def role(self) -> UserRole:
        """Get role as a UserRole enum."""
        try:
            return UserRole[self._role]
        except KeyError:
            return UserRole.STAFF

    @role.setter
    def role(self, value: UserRole):
        """Store the enum name as a string in the database."""
        if isinstance(value, UserRole):
            self._role = value.name
        else:
            raise ValueError(f"Role must be a UserRole enum, got {type(value)}")

    def set_password(self, password):
        """Hash and set password."""
        if not password or len(password) < 8:
            raise InvalidPassword("Password must be at least 8 characters long.")
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check if password matches hash."""
        return check_password_hash(self.password_hash, password)

    def is_manager(self):
        return self.role.value >= UserRole.MANAGER.value

    def is_admin(self):
        return self.role == UserRole.ADMIN

    @classmethod
    def get_player_data(cls, username):
        """Get player data from NetherGames API. Accepts username and XUID"""
        username = username.strip()
        try:
            response = request(f"players/{username}")
            if not response:
                raise UserNotFound(f"User with username '{username}' not found in the NetherGames API.")
            return response
        except UnknownPlayer:
            raise UserNotFound(f"User with username '{username}' not found in the NetherGames API.")
        except MissingAccess:
            raise UserNotFound(f"User with username '{username}' not found in the NetherGames API.")
        except MaintenanceMode:
            raise UserNotFound(f"NetherGames API is in maintenance mode. Try again later.")
        except NetherGamesAPIError as e:
            current_app.logger.error(f"Error fetching player data for '{username}': {e}")
            raise UserNotFound(f"Failed to fetch player data.")

    def validate(self):
        return User.validate_user(self.username)

    @classmethod
    def validate_user(cls, username):
        """ Validates: 
        - User exists in NG API
        - User has a staff rank OR beta tester rank

        Returns:
        - [0] bool of validation (true = valid)
        - [1] data for future use
        """

        data = cls.get_player_data(username)

        try:
            return data['staff'] or any('tester' in rank.lower() for rank in data.get('ranks', [])), data
        except KeyError: raise UserNotFound(f"User with username '{username}' not found in NetherGames API.")

    @classmethod
    def create_user(cls, username, password) -> tuple['User', dict]:
        """
        Create a new user if they exist in NG API and have the right ranks.

        Returns tuple:
        - 'User' class object
        - dict of user API data
        """

        username = username.strip()
        user = cls.query.filter_by(username=username).first()
        if user: raise UserAlreadyExists(username)

        try:
            validated, data = cls.validate_user(username)

            if not validated:
                raise UserNotFound(f"User with username '{username}' is not eligible for system access.")

            xuid = str(data.get('xuid') or '')
            if not xuid:
                raise UserNotFound(f"User with username '{username}' not found in the NetherGames API.")

            if not Whitelist.query.filter_by(xuid=xuid).first():
                raise UserNotWhitelisted(f"User {username} is not whitelisted.")

            is_admin = any('admin' in rank.lower() for rank in data.get('ranks', []))

            user = cls()
            user.xuid = xuid
            user.username = data.get('name') # Handle for casing
            user.role = UserRole.ADMIN if is_admin else UserRole.STAFF
            user.set_password(password)
            return user, data
        except Exception as exc:
            db.session.rollback()
            raise exc

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'

class UserExceptionBase(Exception):
    """Base exception class for User-related errors."""

class UserAlreadyExists(UserExceptionBase):
    """Raised when attempting to create a user that already exists."""
    def __init__(self, username):
        super().__init__(f"User with username '{username}' has already registered.")

class UserNotFound(UserExceptionBase):
    """Raised when a user is not found in the database."""
    def __init__(self, message = "User not found."):
        super().__init__(message)

class InvalidPassword(UserExceptionBase):
    """Raised when an invalid password is provided."""
    def __init__(self, msg="Invalid password provided."):
        super().__init__(msg)
