from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user

main_bp = Blueprint("main", __name__, template_folder="templates", static_folder="static", static_url_path="/static")

@main_bp.route('/')
def home():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))

    return render_template('dashboard.jinja2')
