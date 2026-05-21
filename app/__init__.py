import os
from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()

db = SQLAlchemy()
migrate = None # Placeholder for Flask-Migrate instance, to be initialized in app factory
login_manager = LoginManager()
login_manager.login_view = 'auth.login' # type: ignore
login_manager.login_message_category = 'info'

class Config:
    """Configuration settings for PLX Management System Flask application."""
    DEBUG = os.getenv('DEBUG', 'false').lower() in ['true', '1', 'yes']
    FLASK_ENV = os.getenv('FLASK_ENV', 'production')

    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("No SECRET_KEY set for Flask application. Required for session security.")

    # Respect an explicit non-empty environment variable, but treat empty string as unset
    _db_uri = os.getenv('SQLALCHEMY_DATABASE_URI')
    if _db_uri and _db_uri.strip():
        SQLALCHEMY_DATABASE_URI = _db_uri
    else:
        default_db = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'instance', 'plx.db')
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{default_db}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    NETHERGAMES_API_KEY = os.getenv('NETHERGAMES_API_KEY')
    VERIFY_STAFF_STATUS = os.getenv('VERIFY_STAFF_STATUS', 'true').lower() in ['true', '1', 'yes']

@login_manager.user_loader
def load_user(user_id):
    from app.models.user import User
    return db.session.get(User, int(user_id))

def create_app():
    """Factory function to create and configure the Flask application instance."""
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(Config)

    if app.config.get('FLASK_ENV') == 'production':
        # ProxyFix configuration to ensure IP address detection works correctly
        app.wsgi_app = ProxyFix(
            app.wsgi_app, 
            x_for=1,   # Trusts the X-Forwarded-For header
            x_proto=1, # Trusts the X-Forwarded-Proto header (http vs https)
            x_host=1,  # Trusts the X-Forwarded-Host header
            x_prefix=1 # Trusts the X-Forwarded-Prefix header
        )

    db.init_app(app)
    global migrate
    migrate = Migrate(app, db)
    login_manager.init_app(app)

    from app.auth.routes import auth_bp
    app.register_blueprint(auth_bp)
    from app.main.routes import main_bp
    app.register_blueprint(main_bp)
    from app.admin.routes import admin_bp
    app.register_blueprint(admin_bp)

    return app
