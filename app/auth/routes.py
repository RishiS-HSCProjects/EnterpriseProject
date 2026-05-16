from flask import Blueprint, current_app, jsonify, render_template, redirect, url_for, session, request
from app import db
from app.models.tournament import Tournament
from app.models.user import InvalidPassword, User, UserRole, UserNotFound, UserAlreadyExists
from app.models.whitelist import UserNotWhitelisted, Whitelist
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
            user: User = User.query.filter_by(username=form.username.data).first() # type: ignore

            if user and user.check_password(form.password.data) and (user.validate()[0] if current_app.config.get('VERIFY_STAFF_STATUS') else True):
                user.login()
                flash('Login successful.', 'success')
                return redirect(url_for('main.dashboard'))
            else:
                add_username_error("Invalid username or password.")
                flash_all_form_errors(form)
                save_form_state(form, 'login_form')
                return redirect(url_for('auth.login'))
        except UserNotWhitelisted as exc:
            add_username_error(str(exc))
            flash_all_form_errors(form)
            save_form_state(form, 'login_form')
            return redirect(url_for('auth.login'))
        except Exception as exc:
            current_app.logger.error(f"Unexpected error during user creation: {exc}")
            flash("An unexpected error occurred. Please try again.")
            save_form_state(form, 'login_form')
            return redirect(url_for('auth.login'))
    elif form.errors:
        flash_all_form_errors(form)

    return render_template('login.html', form=form)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    from app.forms import RegistrationForm, VerificationPinForm

    form = RegistrationForm()
    form = restore_form_state(form)

    verify_form = VerificationPinForm()
    show_pin_modal = bool(session.get('pending_registration'))

    return render_template('register.html', form=form, verify_form=verify_form, show_pin_modal=show_pin_modal)

@auth_bp.route('/register/handle/pin', methods=['POST'])
def handle_registration_pin():
    from app.forms import RegistrationForm

    form = RegistrationForm()

    session.pop('pending_registration', None)

    def add_username_error(message: str) -> None:
        form.username.errors = [*form.username.errors, message]

    def fail(code: int = 200):
        flash_all_form_errors(form)
        save_form_state(form, 'registration_form')
        return jsonify({"status": "error"}), code

    if not form.validate_on_submit(): return fail()

    existing_user = User.query.filter_by(username=form.username.data).first()
    if existing_user:
        add_username_error("That username is already registered. Please log in.")
        return fail()

    try:
        user, player_data = User.create_user(
            username=form.username.data,
            password=form.password.data,
        )
    except (UserAlreadyExists, UserNotFound, UserNotWhitelisted) as exc:
        add_username_error(str(exc))
        return fail()
    except InvalidPassword as exc:
        form.password.errors = [*form.password.errors, str(exc)]
        return fail()
    except Exception as exc:
        current_app.logger.error(f"Unexpected error during user creation: {exc}")
        add_username_error("An unexpected error occurred. Please try again.")
        return fail(400)

    discord_id = player_data.get('discordId', None)
    if not discord_id:
        flash('No Discord account linked to this Minecraft account. Please link your Discord account and try again.', 'error')
        return fail()

    from app.auth.utils.verification_utils import send_verification_pin, TooManyAttempts, SuspiciousActivity
    from app.utils.discord_webhook_utils import WebhookError
    try:
        send_verification_pin(user, discord_id=discord_id, request_ip=request.remote_addr) # type: ignore
    except WebhookError as exc:
        current_app.logger.error(f"Webhook error during PIN sending: {exc}")
        flash('An error occurred while sending the verification PIN. Please contact an administrator.', 'error')
        return fail(500)
    except TooManyAttempts:
        flash('Too many verification attempts. Please wait and try again later.', 'error')
        return fail(429)
    except SuspiciousActivity:
        flash('Suspicious activity detected. Please contact an administrator.', 'error')
        return fail(403)
    except Exception as exc:
        current_app.logger.error(f"Unexpected error during PIN sending: {exc}")
        flash('An unexpected error occurred while sending the verification PIN. Please try again later.', 'error')
        return fail(500)

    return jsonify({}), 200

@auth_bp.route('/register/verify/pin', methods=['POST'])
def verify_registration_pin():
    from app.forms import VerificationPinForm
    verify_form = VerificationPinForm()
    pending = session.get('pending_registration')

    if not pending:
        flash('No pending registration found. Please register again.', 'error')
        return jsonify({"status": "error", "message": "No pending registration found. Please register again."}), 400

    if not verify_form.validate_on_submit():
        flash_all_form_errors(verify_form)
        return jsonify({"status": "error", "errors": verify_form.errors}), 400

    def fail(code: int = 200):
        flash_all_form_errors(verify_form)
        return jsonify({"status": "error"}), code

    from app.models.otp_log import OtpLog, OtpLogNotFound, OtpLogExpired, OtpLogInvalidIp
    try:
        otp_verify = OtpLog.verify_otp(pending.get('xuid'), verify_form.pin.data, request.remote_addr) # type: ignore
    except OtpLogNotFound as exc:
        verify_form.pin.errors = [*verify_form.pin.errors, str(exc)]
        return fail()
    except OtpLogExpired as exc:
        verify_form.pin.errors = [*verify_form.pin.errors, str(exc)]
        return fail()
    except OtpLogInvalidIp as exc:
        verify_form.pin.errors = [*verify_form.pin.errors, str(exc)]
        return fail()
    except Exception as exc:
        current_app.logger.error(f"Unexpected error during OTP verification: {exc.with_traceback(exc.__traceback__)}")
        verify_form.pin.errors = [*verify_form.pin.errors, "An unexpected error occurred during OTP verification. Please try again."]
        return fail(500)
    else:
        if not otp_verify:
            verify_form.pin.errors = [*verify_form.pin.errors, "Invalid PIN. Please try again."]
            return fail()

    existing_user = User.query.filter_by(username=pending.get('username')).first()
    if existing_user:
        session.pop('pending_registration')
        flash('That username is already registered. Please log in.', 'warning')
        return jsonify({"status": "error", "message": "That username is already registered. Please log in."}), 409

    wl = Whitelist.query.filter_by(xuid=pending.get('xuid')).first()
    if wl:
        session.pop('pending_registration')
        flash('This account has already been registered. Please log in.', 'warning')
        return jsonify({"status": "error", "message": "This account has already been registered. Please log in."}), 409
    elif not wl:
        current_app.logger.warning(f"Whitelist entry not found for xuid {pending.get('xuid')} during registration verification.")
        flash('Whitelist entry not found for this account. Please contact an administrator.', 'error')
        return fail(403)

    user = User()
    user.xuid = pending.get('xuid')
    user.username = pending.get('username')
    user.role = UserRole[pending.get('role', 'STAFF')]
    user.password_hash = pending.get('password_hash')

    if not user.check_password(verify_form.password.data):
        verify_form.password.errors = [*verify_form.password.errors, 'Incorrect password. Please try again.']
        flash_all_form_errors(verify_form)
        return fail()

    db.session.add(user)
    db.session.commit()

    for tourn in Tournament.query.filter_by(created_by=user.xuid).all():
        tourn.set_created_by(xuid=user.xuid)

    db.session.commit()

    session.pop('pending_registration', None)
    flash('Registration successful. You can now log in.', 'success')
    return jsonify({"status": "success"}), 200

@auth_bp.route('/logout')
def logout():
    from flask_login import logout_user
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth.login'))

@auth_bp.route('/delete')
def delete_account():
    from flask_login import current_user, logout_user
    if current_user.is_authenticated:
        current_user.delete()
        db.session.commit()
        logout_user()
        flash('Your account has been deleted.', 'success')
    else:
        flash('You need to be logged in to delete your account.', 'error')
    return redirect(url_for('auth.login'))
