from flask import Blueprint, current_app, render_template, redirect, url_for, session
import secrets
from app import db
from app.models.user import User, UserNotFound, UserAlreadyExists
from app.utils.utils import (
    flash_all_form_errors, flash, save_form_state, restore_form_state
)

auth_bp = Blueprint("auth", __name__, template_folder="templates", static_folder="static", static_url_path="/auth/static")

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    from app.forms import LoginForm
    form = LoginForm()
    form = restore_form_state(form)

    def add_username_error(message: str) -> None:
        form.username.errors = [*form.username.errors, message]

    if form.validate_on_submit():
        try:
            user = User.query.filter_by(username=form.username.data).first()

            if user and user.check_password(form.password.data):
                user.login()
                flash('Login successful.', 'success')
                return redirect(url_for('auth.login'))
            else:
                add_username_error("Invalid username or password.")
                flash_all_form_errors(form)
                save_form_state(form, 'login_form')
                return redirect(url_for('auth.login'))
        except Exception as exc:
            add_username_error(str(exc))
            flash_all_form_errors(form)
            save_form_state(form, 'login_form')
            return redirect(url_for('auth.login'))
    elif form.errors:
        flash_all_form_errors(form)

    return render_template('login.jinja2', form=form)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    from app.forms import RegistrationForm, VerificationPinForm

    form = RegistrationForm()
    form = restore_form_state(form)

    verify_form = VerificationPinForm()
    show_pin_modal = bool(session.get('pending_registration'))

    def add_username_error(message: str) -> None:
        form.username.errors = [*form.username.errors, message]

    if form.validate_on_submit():
        try:
            user, player_data = User.create_user(form.username.data, form.password.data)
            pin = f"{secrets.randbelow(1_000_000):06d}"

            from bcrypt import hashpw, gensalt

            session['pending_registration'] = {
                'xuid': user.xuid,
                'username': user.username,
                'password_hash': user.password_hash,
                'role': user.role,
                'hashed_pin': hashpw(pin.encode(), gensalt()),
            }

            discord_id = player_data.get('discordId', None)

            if discord_id:
                # TODO: Add device blocking capabilities if the user says they didn't request a PIN, to prevent
                # abuse of the registration system. This would require tracking pending registrations and their
                # associated IP addresses/devices, and allowing users to block further attempts from those sources
                # if they receive an unexpected PIN.
                msg = f"<@{discord_id}>, please use the following PIN to verify your account: `{pin}`"
                from app.utils.discord_webhook_utils import send, ChannelWebhookUrl
                if send(ChannelWebhookUrl.SECURE_WEBHOOK_URL, username="NetherGames PLX Registration", content=msg):
                    flash('Verification PIN sent to Discord.', 'success')
                else:
                    current_app.logger.warning(f"Failed to send PIN to Discord for user {form.username.data}, showing PIN in-app.")
                    flash(f"Verification PIN: {pin}", 'info')
            else:
                add_username_error("No Discord account linked to this user. Please link a Discord account and try again.")
                flash_all_form_errors(form)
                return render_template('register.jinja2', form=form, verify_form=verify_form, show_pin_modal=False)

            flash('Enter the verification PIN to complete registration.', 'warning')
            return redirect(url_for('auth.register'))
        except UserAlreadyExists as exc:
            add_username_error(str(exc))
            flash_all_form_errors(form)
            save_form_state(form, 'register_form')
            return redirect(url_for('auth.register'))
        except UserNotFound as exc:
            add_username_error(str(exc))
            flash_all_form_errors(form)
            save_form_state(form, 'register_form')
            return redirect(url_for('auth.register'))
        except Exception as exc:
            add_username_error("An unexpected error occurred. Please try again.")
            flash_all_form_errors(form)
            current_app.logger.error(f"Error during registration: {exc}")
            save_form_state(form, 'register_form')
            return redirect(url_for('auth.register'))
    elif form.errors:
        flash_all_form_errors(form)

    return render_template('register.jinja2', form=form, verify_form=verify_form, show_pin_modal=show_pin_modal)


@auth_bp.route('/register/verify-pin', methods=['POST'])
def verify_registration_pin():
    from app.forms import RegistrationForm, VerificationPinForm

    form = RegistrationForm()
    verify_form = VerificationPinForm()
    pending = session.get('pending_registration')

    if not pending:
        flash('No pending registration found. Please register again.', 'error')
        return redirect(url_for('auth.register'))

    if not verify_form.validate_on_submit():
        flash_all_form_errors(verify_form)
        return render_template('register.jinja2', form=form, verify_form=verify_form, show_pin_modal=True)

    from bcrypt import checkpw
    if not checkpw(verify_form.pin.data.encode(), pending.get('hashed_pin')):
        verify_form.pin.errors = [*verify_form.pin.errors, 'Incorrect PIN. Please try again.']
        flash_all_form_errors(verify_form)
        return render_template('register.jinja2', form=form, verify_form=verify_form, show_pin_modal=True)

    existing_user = User.query.filter_by(username=pending.get('username')).first()
    if existing_user:
        session.pop('pending_registration', None)
        flash('That username is already registered. Please log in.', 'warning')
        return redirect(url_for('auth.login'))

    user = User()
    user.xuid = pending.get('xuid')
    user.username = pending.get('username')
    user.role = pending.get('role')
    user.password_hash = pending.get('password_hash')

    db.session.add(user)
    db.session.commit()
    session.pop('pending_registration', None)
    flash('Registration successful. You can now log in.', 'success')
    return redirect(url_for('auth.login'))
