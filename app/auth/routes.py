from flask import Blueprint, current_app, render_template, redirect, url_for

from app import db
from app.models.user import User, UserNotFound, UserAlreadyExists
from app.utils import flash_all_form_errors, flash

auth_bp = Blueprint("auth", __name__, template_folder="templates", static_folder="static", static_url_path="/auth/static")

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    from app.forms import LoginForm

    form = LoginForm()

    def add_username_error(message: str) -> None:
        form.username.errors = [*form.username.errors, message]

    if form.validate_on_submit():
        try:
            user = User.query.filter_by(username=form.username.data).first()

            try:
                User.validate_user(user)
            except UserNotFound as exc:
                add_username_error("Invalid username or password.")
                flash_all_form_errors(form)
                return render_template('login.jinja2', form=form)

            if user and user.check_password(form.password.data):
                flash('Login successful.', 'success')
                return redirect(url_for('auth.login'))
            else:
                add_username_error("Invalid username or password.")
                flash_all_form_errors(form)
        except Exception as exc:
            add_username_error(str(exc))
            flash_all_form_errors(form)
    elif form.errors:
        flash_all_form_errors(form)

    return render_template('login.jinja2', form=form)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    from app.forms import RegistrationForm

    form = RegistrationForm()

    def add_username_error(message: str) -> None:
        form.username.errors = [*form.username.errors, message]

    if form.validate_on_submit():
        try:
            user = User.create_user(form.username.data, form.password.data)
            db.session.add(user)
            db.session.commit()
            flash('Registration successful. You can now log in.', 'success')
            return redirect(url_for('auth.login'))
        except UserAlreadyExists as exc:
            add_username_error(str(exc))
            flash_all_form_errors(form)
        except UserNotFound as exc:
            add_username_error(str(exc))
            flash_all_form_errors(form)
        except Exception as exc:
            add_username_error("An unexpected error occurred. Please try again.")
            flash_all_form_errors(form)
            current_app.logger.error(f"Error during registration: {exc}")
        return redirect(url_for('auth.register'))
    elif form.errors:
        flash_all_form_errors(form)

    return render_template('register.jinja2', form=form)