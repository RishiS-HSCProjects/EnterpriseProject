from dataclasses import dataclass

from flask import Blueprint, render_template, redirect, url_for, request, current_app, jsonify
from flask_login import current_user, login_required
from app.models.tournament import Tournament, TournamentArchiveException, TournamentPrizes
from app.utils.utils import flash, flash_all_form_errors, restore_form_state
from app.utils.discord_webhook_utils import ChannelWebhookUrl, format_placement_lines, format_prize_lines, send as discord_send
from time import time
from datetime import datetime, UTC

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
        start_unix = add_form.start_unix.data
        end_unix = add_form.end_unix.data
        round_count = add_form.round_count.data
        name = (add_form.name.data or '').strip()
        assert start_unix is not None
        assert end_unix is not None
        assert round_count is not None

        # Check for time overlap with existing tournaments
        overlap = Tournament.query.filter(
            Tournament.start_unix < end_unix,
            Tournament.end_unix > start_unix
        ).first()
        if overlap:
            flash(f'Time overlap with tournament "{overlap.name}" (unix {overlap.start_unix}-{overlap.end_unix})', 'error')
        else:
            Tournament.create(
                name=name,
                start_unix=start_unix,
                end_unix=end_unix,
                round_count=round_count,
                created_by=current_user.id,
                prizes=TournamentPrizes(
                    overall_first=(add_form.global_first_prize.data or '').strip(),
                    overall_second=(add_form.global_second_prize.data or '').strip(),
                    overall_third=(add_form.global_third_prize.data or '').strip(),
                    round_first=(add_form.round_first_prize.data or '').strip(),
                    round_second=(add_form.round_second_prize.data or '').strip(),
                    round_third=(add_form.round_third_prize.data or '').strip(),
                )
            )
            flash('Tournament added successfully!', 'success')
            return redirect(url_for('main.scheduler'))
    elif request.method == 'POST':
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

@main_bp.route('/scheduler/<int:tournament_id>', methods=['GET', 'POST'])
@login_required
def tournament_editor(tournament_id: int):
    from app.forms import AddTournamentForm

    tourney = Tournament.query.get_or_404(tournament_id)
    if not tourney:
        flash('Tournament not found', 'error')
        return redirect(url_for('main.scheduler'))

    if tourney.is_expired and not tourney.tournament_info_discord_status:
        tourney.tournament_info_discord_status = True
        from app import db
        db.session.commit()

    form = restore_form_state(AddTournamentForm())

    # Autofill fields from tournament object on GET request
    if request.method == 'GET' or not form.is_submitted():
        form.name.data = tourney.name
        form.start_unix.data = tourney.start_unix
        form.end_unix.data = tourney.end_unix
        form.round_count.data = tourney.round_count
        form.discord_message.data = getattr(tourney, 'tournament_info_discord_message', None) or ''
        prizes = getattr(tourney, 'prizes', {}) or {}
        form.global_first_prize.data = prizes.get('overall_first', '')
        form.global_second_prize.data = prizes.get('overall_second', '')
        form.global_third_prize.data = prizes.get('overall_third', '')
        form.round_first_prize.data = prizes.get('round_first', '')
        form.round_second_prize.data = prizes.get('round_second', '')
        form.round_third_prize.data = prizes.get('round_third', '')

    # Handle form submission for edits
    if form.validate_on_submit():
        start_unix = form.start_unix.data
        end_unix = form.end_unix.data
        round_count = form.round_count.data
        assert start_unix is not None
        assert end_unix is not None
        assert round_count is not None

        # Check for time overlap with other tournaments
        overlap = Tournament.query.filter(
            Tournament.id != tourney.id,
            Tournament.start_unix < end_unix,
            Tournament.end_unix > start_unix
        ).first()
        if overlap:
            flash(f'Time overlap with tournament "{overlap.name}" (unix {overlap.start_unix}-{overlap.end_unix})', 'error')
        else:
            tourney.name = (form.name.data or '').strip()
            tourney.start_unix = int(start_unix)
            tourney.end_unix = int(end_unix)
            if round_count < 1:
                flash('Round count must be at least 1', 'error')
            else: tourney.round_count = int(round_count)

            tourney.prizes = {
                'overall_first': (form.global_first_prize.data or '').strip(),
                'overall_second': (form.global_second_prize.data or '').strip(),
                'overall_third': (form.global_third_prize.data or '').strip(),
                'round_first': (form.round_first_prize.data or '').strip(),
                'round_second': (form.round_second_prize.data or '').strip(),
                'round_third': (form.round_third_prize.data or '').strip(),
            }
            if not tourney.tournament_info_discord_status:
                if form.discord_message.data and form.discord_message.data.strip() != tourney.tournament_info_discord_message:
                    tourney.tournament_info_discord_message = form.discord_message.data.strip()
            else: flash('Tournament info Discord message is locked and cannot be edited.', 'error')

            from app import db
            db.session.commit()
            flash('Tournament updated', 'success')
            return redirect(url_for('main.tournament_editor', tournament_id=tourney.id))
    elif request.method == 'POST':
        flash_all_form_errors(form)

    # leaderboard views (current round and overall)
    current_round = None
    if tourney.is_active:
        # approximate current round
        elapsed = int(time()) - tourney.start_unix
        if tourney.round_duration > 0:
            current_round = min(tourney.round_count, max(1, int(elapsed // tourney.round_duration) + 1))

    leaderboard_overall = tourney.get_leaderboard(round_num=None)
    if tourney.is_active and current_round:
        round_numbers = list(range(1, current_round + 1))
    elif tourney.is_expired:
        round_numbers = list(range(1, tourney.round_count + 1))
    else:
        round_numbers = []

    round_leaderboards = [
        {
            'round_num': round_num,
            'leaderboard': tourney.get_leaderboard(round_num=round_num),
        }
        for round_num in round_numbers
    ]
    selected_round = current_round if current_round else (round_leaderboards[-1]['round_num'] if round_leaderboards else None)
    cache_stats_locked = tourney.is_archived()

    now_ts = int(datetime.now(UTC).timestamp())

    def _relative(ts: int) -> str:
        diff = ts - now_ts
        abs_diff = abs(diff)
        if abs_diff < 60:
            amount = abs_diff
            unit = 's'
        elif abs_diff < 3600:
            amount = abs_diff // 60
            unit = 'm'
        elif abs_diff < 86400:
            amount = abs_diff // 3600
            unit = 'h'
        else:
            amount = abs_diff // 86400
            unit = 'd'

        if diff == 0:
            return 'now'
        if diff > 0:
            return f'in {amount}{unit}'
        return f'{amount}{unit} ago'

    start_dt = datetime.fromtimestamp(tourney.start_unix, UTC)
    end_dt = datetime.fromtimestamp(tourney.end_unix, UTC)

    epoch_details = {
        'start_gmt': start_dt.strftime('%a, %d %b %Y %H:%M:%S GMT'),
        'end_gmt': end_dt.strftime('%a, %d %b %Y %H:%M:%S GMT'),
        'start_local_title': f"Local: {start_dt.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}",
        'end_local_title': f"Local: {end_dt.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}",
        'start_relative_title': f"Relative: {_relative(tourney.start_unix)}",
        'end_relative_title': f"Relative: {_relative(tourney.end_unix)}",
    }

    return render_template(
        'tournament_detail.html',
        form=form,
        tournament=tourney,
        leaderboard_overall=leaderboard_overall,
        current_round=current_round,
        round_leaderboards=round_leaderboards,
        selected_round=selected_round,
        cache_stats_locked=cache_stats_locked,
        epoch_details=epoch_details,
    )


@main_bp.route('/scheduler/<int:tournament_id>/discord/send', methods=['POST'])
@login_required
def tournament_send_discord(tournament_id: int):
    if not current_user.is_manager():
        flash('Access denied: Managers only.', 'error')
        return redirect(url_for('main.tournament_editor', tournament_id=tournament_id)), 403

    tourney = Tournament.query.get_or_404(tournament_id)
    if tourney.tournament_info_discord_status or tourney.is_expired:
        # Prevents resending announcements and also ensures expired tournaments that missed the announcement window are still marked as having sent the announcement (since the announcement is locked after expiration)
        if not tourney.tournament_info_discord_status:
            tourney.tournament_info_discord_status = True
            from app import db
            db.session.commit()
        flash('Tournament announcement is locked and cannot be sent again.', 'error')
        return redirect(url_for('main.tournament_editor', tournament_id=tourney.id)), 403

    message = (tourney.tournament_info_discord_message or request.form.get('message') or '').strip()

    round_hours = max(0.5, round(tourney.round_duration / 3600, 1))
    message_content = (
        f"## :mega: Tournament Announcement\n\n"
        f"This tournament will start on <t:{tourney.start_unix}:F> and will conclude on <t:{tourney.end_unix}:F>.\n"
        f"It will finish <t:{tourney.end_unix}:R>.\n\n"
        f"**Each round will last {round_hours} hour{'' if round_hours == 1 else 's'}.**"
    )

    if message:
        message_content += f"\n\n### Additional Info\n{message}"

    message_content += (
        "\n\nSimply join a Skywars Solos game and play as you would normally do. "
        "Your kills are automatically counted and tracked at https://ngmc.co/tournament"
    )

    prizes = getattr(tourney, 'prizes', {}) or {}
    if any(prizes.get(key) for key in ['overall_first', 'overall_second', 'overall_third']):
        message_content += (
            "\n\n## :trophy: Overall Ranking Prizes\n"
            f"{format_prize_lines({
                'first': prizes.get('overall_first', 'TBA'),
                'second': prizes.get('overall_second', 'TBA'),
                'third': prizes.get('overall_third', 'TBA'),
            })}"
            "\n\nOverall Ranking rewards the top 3 players across all rounds. Overall Ranking prizes are cumulative with Per-Round Rewards. Tournament rules and prizes are subject to change. Please follow tournament-info for updates."
        )
    if any(prizes.get(key) for key in ['round_first', 'round_second', 'round_third']):
        message_content += (
            "\n\n## :gift: Per-Round Prizes\n"
            f"{format_prize_lines({
                'first': prizes.get('round_first', 'TBA'),
                'second': prizes.get('round_second', 'TBA'),
                'third': prizes.get('round_third', 'TBA'),
            })}"
            "\n\nTitan Rank rewards are not transferable. Per-round Titan Rank rewards are non-cumulative, however, overall ranking players will receive their overall-ranking Titan prize on top of their round-ranking Titan prize (if applicable). Tournament rules and prizes are subject to change. Please follow tournament-info for updates."
        )

    try:
        ok = discord_send(
            location=ChannelWebhookUrl.ANNOUNCEMENT_WEBHOOK_URL,
            content=message_content,
        )
        if ok:
            # TODO: Enable. Disabled for testing purposes to allow resending
            # tourney.tournament_info_discord_status = True
            # from app import db
            # db.session.commit()
            flash('Discord message sent', 'success')
        else:
            flash('Failed to send Discord message', 'error')
    except Exception:
        flash('Error sending Discord message. Please contact an administrator.', 'error')

    return redirect(url_for('main.tournament_editor', tournament_id=tourney.id))

@main_bp.route('/scheduler/<int:tournament_id>/prizes/send', methods=['POST'])
@login_required
def tournament_send_prizes_discord(tournament_id: int):
    if not current_user.is_manager():
        flash('Access denied: Managers only.', 'error')
        return redirect(url_for('main.tournament_editor', tournament_id=tournament_id)), 403

    tourney = Tournament.query.get_or_404(tournament_id)

    if not tourney.is_expired:
        flash('Prize announcement is locked until the tournament ends.', 'error')
        return redirect(url_for('main.tournament_editor', tournament_id=tourney.id)), 403

    if tourney.awards_distributed:
        flash('Prize announcement is locked and cannot be sent again.', 'error')
        return redirect(url_for('main.tournament_editor', tournament_id=tourney.id)), 403

    prizes = getattr(tourney, 'prizes', {}) or {}

    overall_prizes = {
        'first': prizes.get('overall_first', ''),
        'second': prizes.get('overall_second', ''),
        'third': prizes.get('overall_third', ''),
    }

    round_prizes = {
        'first': prizes.get('round_first', ''),
        'second': prizes.get('round_second', ''),
        'third': prizes.get('round_third', ''),
    }

    overall_entries = tourney.get_leaderboard(round_num=None).get_entries(limit=3)
    overall_text = format_placement_lines(overall_entries, label='kills!')

    round_sections = []
    for round_num in range(1, tourney.round_count + 1):
        entries = tourney.get_leaderboard(round_num=round_num).get_top(3)
        round_sections.append(
            f"**Round {round_num}**\n{format_placement_lines(entries)}"
        )

    rounds_text = "\n\n".join(round_sections)

    optional_message = (tourney.tournament_info_discord_message or '').strip()

    message = (
        f"## {tourney.name} Tournament Rewards!\n\n"
    )

    if optional_message:
        message += f"{optional_message}\n\n"

    message += (
        f"## :trophy: **OVERALL WINNERS**\n\n"
        f"Congratulations to these players with the most kills across the board!\n\n"
        f"{overall_text}\n\n"

        f"## :bar_chart: **ROUND WINNERS**\n\n"
        f"{rounds_text}\n\n"

        f"## :gift: **PRIZES**\n"
        f"-# All prizes have now been distributed. Additions are awarded to accounts automatically.\n\n"
        f"{format_prize_lines(round_prizes)}\n\n"
        f"{format_prize_lines(overall_prizes)}"
    )

    try:
        discord_send(
            location=ChannelWebhookUrl.ANNOUNCEMENT_WEBHOOK_URL,
            content=message
        )
    except Exception:
        flash('Error sending Discord message. Please contact an administrator.', 'error')
        return redirect(url_for('main.tournament_editor', tournament_id=tourney.id))

    # TODO: Enable. Disabled for testing purposes to allow resending
    # tourney.awards_distributed = True
    # from app import db
    # db.session.commit()

    flash('Prize announcement sent', 'success')
    return redirect(url_for('main.tournament_editor', tournament_id=tourney.id))
@main_bp.route('/scheduler/<int:tournament_id>/cache/stats', methods=['POST'])
@login_required
def tournament_cache_stats(tournament_id: int):
    tourney = Tournament.query.get_or_404(tournament_id)

    def _round_keys() -> set[int]:
        archives = tourney.archives or {}
        if not isinstance(archives, dict):
            return set()
        rounds_data = archives.get('rounds', {})
        if not isinstance(rounds_data, dict):
            return set()
        return {int(key) for key in rounds_data.keys() if str(key).isdigit()}

    def _format_rounds(rounds: list[int], singular_label: str = 'round', plural_label: str = 'rounds') -> str:
        if not rounds:
            return ''
        if len(rounds) == 1:
            return f'{singular_label} {rounds[0]}'
        if len(rounds) == 2:
            return f'{plural_label} {rounds[0]} and {rounds[1]}'
        return f"{plural_label} {', '.join(map(str, rounds[:-1]))} and {rounds[-1]}"

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    before_rounds = _round_keys()
    
    try:
        failures = list(tourney.archive_stats())
        failed_rounds = sorted(round_num for round_num, ok in failures if ok is False)
        after_rounds = _round_keys()
        cached_rounds = sorted(after_rounds - before_rounds)

        if cached_rounds:
            message = f"Successfully cached {_format_rounds(cached_rounds)}"
            if is_ajax:
                return jsonify({'success': True, 'message': message, 'cached_rounds': cached_rounds, 'failed_rounds': failed_rounds})
            flash(message, 'success')
        elif failed_rounds:
            message = f"Failed to cache {_format_rounds(failed_rounds)}"
            if is_ajax:
                return jsonify({'success': False, 'message': message, 'cached_rounds': [], 'failed_rounds': failed_rounds}), 500
            flash(message, 'error')
        else:
            message = 'No finished rounds available to cache.'
            if is_ajax:
                return jsonify({'success': False, 'message': message, 'cached_rounds': [], 'failed_rounds': []}), 400
            flash(message, 'error')
    except TournamentArchiveException as exc:
        message = f'Error archiving stats: {str(exc)}'
        if is_ajax:
            return jsonify({'success': False, 'message': message, 'cached_rounds': [], 'failed_rounds': []}), 400
        flash(message, 'error')
    except Exception:
        current_app.logger.exception('Error caching tournament stats')
        message = 'Unexpected error caching tournament stats'
        if is_ajax:
            return jsonify({'success': False, 'message': message, 'cached_rounds': [], 'failed_rounds': []}), 500
        flash(message, 'error')
    
    return redirect(url_for('main.tournament_editor', tournament_id=tourney.id))
