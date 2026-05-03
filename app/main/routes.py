from dataclasses import dataclass

from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user, login_required
from app.models.tournament import Tournament
from app.utils.utils import flash, flash_all_form_errors, restore_form_state

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

@main_bp.route('/scheduler', methods=['GET', 'POST'])
@login_required
def scheduler(open_add_modal=False):
    from app.forms import AddTournamentForm
    from datetime import UTC, datetime

    now = int(datetime.now(UTC).timestamp())

    previous_tournaments = (
        Tournament.query
        .filter(Tournament.end_unix < now)
        .order_by(Tournament.end_unix.desc())
        .limit(2)
        .all()
        or []
    )
    # reverse the list so most-recent is first
    previous_tournaments = list(reversed(previous_tournaments))
    current_tournament = (
        Tournament.query
        .filter(Tournament.start_unix <= now, Tournament.end_unix >= now)
        .order_by(Tournament.start_unix.asc())
        .first()
    )
    future_tournaments = (
        Tournament.query
        .filter(Tournament.start_unix > now)
        .order_by(Tournament.start_unix.asc())
        .all()
    )

    add_form = restore_form_state(AddTournamentForm())

    if add_form.validate_on_submit():
        Tournament.create(
            name=add_form.name.data,
            start_unix=add_form.start_unix.data,
            end_unix=add_form.end_unix.data,
            round_count=add_form.round_count.data,
            created_by=current_user.id
        )
        flash('Tournament added successfully!', 'success')
        return redirect(url_for('main.scheduler'))
    else:
        flash_all_form_errors(add_form)

    return render_template(
        'scheduler.html',
        add_form=add_form,
        previous_tournaments=previous_tournaments,
        current_tournament=current_tournament,
        future_tournaments=future_tournaments,
        show_add_modal=open_add_modal or add_form.errors,
    )

@main_bp.route('/admin')
@login_required
def admin_panel():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    if not current_user.is_admin():
        return "Access denied: Admins only.", 403

    return 'Admin Panel - Coming Soon!'
