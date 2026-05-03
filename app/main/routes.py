from dataclasses import dataclass

from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user, login_required

main_bp = Blueprint("main", __name__, template_folder="templates", static_folder="static", static_url_path="/main/static")

@main_bp.route('/')
def dashboard():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))

    @dataclass
    class KPI:
        title: str
        value: str
        unit: str = ""
        hover_text: str = ""

    # Placeholder KPIs
    kpis = [
        KPI(title="Days till next tournament", value="12", unit="days", hover_text="Number of tournaments hosted"),
        KPI(title="Active Players", value="350", unit="players", hover_text="Number of active players"),
        KPI(title="Upcoming Events", value="3", unit="events", hover_text="Tournaments scheduled in the next month")
    ]

    return render_template('dashboard.html', kpis=kpis)

@main_bp.route('/scheduler')
@login_required
def scheduler():
    return render_template('scheduler.html')

@main_bp.route('/admin')
@login_required
def admin_panel():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    if not current_user.is_admin():
        return "Access denied: Admins only.", 403

    return 'Admin Panel - Coming Soon!'
