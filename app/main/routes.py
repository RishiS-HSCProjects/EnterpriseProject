from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user

main_bp = Blueprint("main", __name__, template_folder="templates", static_folder="static", static_url_path="/main/static")

@main_bp.route('/')
def dashboard():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))

    return render_template('dashboard.html')

@main_bp.route('/schedule')
def schedule():
    return 'Schedule page - Coming Soon!'

@main_bp.route('/planner')
def planner():
    return 'Planner page - Coming Soon!'

@main_bp.route('/admin')
def admin_panel():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    if not current_user.is_admin():
        return "Access denied: Admins only.", 403

    return 'Admin Panel - Coming Soon!'
