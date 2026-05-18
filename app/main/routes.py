from dataclasses import dataclass
from flask import Blueprint, render_template, redirect, url_for, request, current_app, jsonify
from flask_login import current_user, login_required
from app.models.tournament import Tournament, TournamentArchiveException, TournamentPrizes
from app.utils.utils import flash, flash_all_form_errors, restore_form_state, save_form_state
from app.utils.discord_webhook_utils import ChannelWebhookUrl, format_placement_lines, format_prize_lines, send as discord_send
from time import time
from datetime import datetime, UTC

main_bp = Blueprint("main", __name__, template_folder="templates", static_folder="static", static_url_path="/main/static")

@main_bp.route('/')
def dashboard():
    @dataclass
    class KPI:
        title: str
        value: str
        detail: str = ""
        hover_text: str = ""
        href: str | None = None

    def _format_days(value: int) -> str:
        return "1" if value == 1 else str(value)

    def _format_day_label(value: int) -> str:
        return "day" if value == 1 else "days"

    def _format_round_duration(seconds: float) -> str:
        total_seconds = max(0, int(round(seconds)))
        if total_seconds < 60:
            return f"{total_seconds} seconds"
        if total_seconds < 3600:
            minutes = total_seconds // 60
            remainder = total_seconds % 60
            return f"{minutes}m {remainder}s"
        hours = total_seconds // 3600
        remainder = total_seconds % 3600
        minutes = remainder // 60
        return f"{hours}h {minutes}m"

    now_ts = int(datetime.now(UTC).timestamp())
    tournaments = Tournament.query.order_by(Tournament.start_unix.asc()).all()

    active_tournament = next((t for t in tournaments if t.start_unix <= now_ts <= t.end_unix), None)
    next_tournament = next((t for t in tournaments if t.start_unix > now_ts), None)
    last_tournament = next((t for t in reversed(tournaments) if t.end_unix < now_ts), None)

    kpis: list[KPI] = []

    if active_tournament:
        current_round = min(
            active_tournament.round_count,
            max(1, int((now_ts - active_tournament.start_unix) // active_tournament.round_duration) + 1),
        )
        kpis.append(KPI(
            title="Active Tournament",
            value=str(current_round),
            detail=f"of {active_tournament.round_count} rounds",
            hover_text=f"{active_tournament.name} is currently running.",
            href=url_for('main.tournament_editor', tournament_id=active_tournament.id)
        ))
        kpis.append(KPI(
            title="Status",
            value="LIVE",
            detail=active_tournament.name,
            hover_text=f"Started {datetime.fromtimestamp(active_tournament.start_unix, UTC).strftime('%a, %d %b %Y %H:%M UTC')}"
        ))
        kpis.append(KPI(
            title="Round Duration",
            value=_format_round_duration(active_tournament.round_duration),
            detail=f"{str(max(1, int(round(active_tournament.round_duration))))} seconds per round",
            hover_text=f"Each round lasts about {active_tournament.round_duration:.0f} seconds."
        ))
    elif next_tournament:
        days_until = max(0, (next_tournament.start_unix - now_ts + 86399) // 86400)
        kpis.append(KPI(
            title="Days to Next Tourney",
            value=_format_days(days_until),
            detail=_format_day_label(days_until),
            hover_text=f"Next tournament: {next_tournament.name}"
        ))
        kpis.append(KPI(
            title="Status",
            value="UP NEXT",
            detail=next_tournament.name,
            hover_text="No tournament is currently running."
        ))
        kpis.append(KPI(
            title="Round Duration",
            value=_format_round_duration(next_tournament.round_duration),
            detail=f"{str(max(1, int(round(next_tournament.round_duration))))} seconds per round",
            hover_text=f"Future tournament round length: {next_tournament.round_duration:.0f} seconds."
        ))
    else:
        if tournaments:
            days_ago = max(0, (now_ts - tournaments[-1].end_unix) // 86400)
            kpis.append(KPI(
                title="Last Tournament",
                value=_format_days(days_ago),
                detail=f"{_format_day_label(days_ago)} ago",
                hover_text=f"Last tournament: {tournaments[-1].name}"
            ))
        else:
            kpis.append(KPI(
                title="Last Tournament",
                value="0",
                detail="No tournaments yet",
                hover_text="Create the first tournament to populate the dashboard."
            ))

        kpis.append(KPI(
            title="Status",
            value="IDLE",
            detail="No active tournament",
            hover_text="No tournament is currently active."
        ))

        kpis.append(KPI(
            title="Round Duration",
            value="0",
            detail="N/A until a tournament exists",
            hover_text="Round duration is only available once a tournament exists."
        ))

    if last_tournament:
        overall_leaderboard = last_tournament.get_leaderboard(round_num=None)
        last_winner = overall_leaderboard.get_entries(limit=1)
        if last_winner:
            winner = last_winner[0]
            kpis.append(KPI(
                title="Last Overall Winner",
                value=str(winner.score),
                detail=f"{winner.player}",
                hover_text=f"Top performer from {last_tournament.name}.",
                href=url_for('main.tournament_editor', tournament_id=last_tournament.id)
            ))
        else:
            kpis.append(KPI(
                title="Last Overall Winner",
                value="0",
                detail=f"{last_tournament.name} no leaderboard data",
                hover_text="The last tournament has no archived overall leaderboard yet.",
                href=url_for('main.tournament_editor', tournament_id=last_tournament.id)
            ))
    else:
        kpis.append(KPI(
            title="Last Overall Winner",
            value="0",
            detail="No finished tournaments yet",
            hover_text="There is no completed tournament to summarize yet."
        ))

    return render_template('dashboard.html', kpis=kpis)

@main_bp.route('/scheduler', methods=['GET', 'POST'])
def scheduler(open_add_modal=False):
    from app.forms import AddTournamentForm

    kwargs = {}
    now = int(datetime.now(UTC).timestamp())

    # 1. Fetch Tournament Data
    previous = Tournament.query.filter(Tournament.end_unix < now).order_by(Tournament.end_unix.desc()).limit(2).all() or []

    kwargs.update({
        'previous_tournaments': list(reversed(previous)),
        'current_tournament': Tournament.query.filter(Tournament.start_unix <= now, Tournament.end_unix >= now).order_by(Tournament.start_unix.asc()).first(),
        'future_tournaments': Tournament.query.filter(Tournament.start_unix > now).order_by(Tournament.start_unix.asc()).all()
    })

    # 2. Handle Form Logic
    add_form = None
    if current_user.is_authenticated:
        add_form = restore_form_state(AddTournamentForm())

        if add_form.validate_on_submit():
            # Check for time overlap
            start, end = add_form.start_unix.data, add_form.end_unix.data
            overlap = Tournament.query.filter(Tournament.start_unix < end, Tournament.end_unix > start).first()

            if overlap:
                flash(f'Time overlap with tournament "{overlap.name}"', 'error')
            else:
                Tournament.create(
                    name=(add_form.name.data or '').strip(),
                    start_unix=start,
                    end_unix=end,
                    round_count=add_form.round_count.data,
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

    # 3. Consolidate Remaining UI State
    kwargs['add_form'] = add_form
    kwargs['show_add_modal'] = open_add_modal or (add_form.errors if add_form else False)

    return render_template('scheduler.html', **kwargs)

@main_bp.route('/scheduler/<int:tournament_id>', methods=['GET', 'POST'])
def tournament_editor(tournament_id: int):
    from app.forms import AddTournamentForm
    from app import db

    tourney = Tournament.query.get_or_404(tournament_id)
    kwargs = {'tournament': tourney}
    if not tourney.tournament_info_discord_status and tourney.is_expired:
        tourney.tournament_info_discord_status = True
        db.session.commit()

    form = AddTournamentForm(request.form if request.method == 'POST' else None)
    if request.method == 'GET':
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
    elif request.method == 'POST':
        save_form_state(form, form_id='tournament_editor')

    if current_user.is_authenticated:
        form = restore_form_state(form)

        if form.validate_on_submit():
            start, end, rounds = form.start_unix.data, form.end_unix.data, form.round_count.data

            overlap = Tournament.query.filter(
                Tournament.id != tourney.id,
                Tournament.start_unix < end,
                Tournament.end_unix > start
            ).first()

            if overlap:
                flash(f'Time overlap with tournament "{overlap.name}"', 'error')
            elif rounds < 1:
                flash('Round count must be at least 1', 'error')
            else:
                tourney.name = (form.name.data or '').strip()
                tourney.start_unix, tourney.end_unix, tourney.round_count = int(start), int(end), int(rounds)
                tourney.prizes = {
                    'overall_first': (form.global_first_prize.data or '').strip(),
                    'overall_second': (form.global_second_prize.data or '').strip(),
                    'overall_third': (form.global_third_prize.data or '').strip(),
                    'round_first': (form.round_first_prize.data or '').strip(),
                    'round_second': (form.round_second_prize.data or '').strip(),
                    'round_third': (form.round_third_prize.data or '').strip(),
                }

                if not tourney.tournament_info_discord_status:
                    tourney.tournament_info_discord_message = (form.discord_message.data or '').strip()

                db.session.commit()
                flash('Tournament updated', 'success')
                return redirect(url_for('main.tournament_editor', tournament_id=tourney.id))

        elif request.method == 'POST':
            flash_all_form_errors(form)

    current_round = None
    if tourney.is_active and tourney.round_duration > 0:
        elapsed = int(time()) - tourney.start_unix
        current_round = min(tourney.round_count, max(1, int(elapsed // tourney.round_duration) + 1))

    if tourney.is_active and current_round:
        round_numbers = list(range(1, current_round + 1))
    elif tourney.is_expired:
        round_numbers = list(range(1, tourney.round_count + 1))
    else:
        round_numbers = []

    now_ts = int(datetime.now(UTC).timestamp())
    start_dt = datetime.fromtimestamp(tourney.start_unix, UTC)
    end_dt = datetime.fromtimestamp(tourney.end_unix, UTC)

    # Build round leaderboards
    round_leaderboards = []
    all_disqualified_players = {}  # {player_name: [list of {round, punishments}]}

    for r in round_numbers:
        round_data = {
            'round_num': r,
            'leaderboard': tourney.get_leaderboard(round_num=r),
        }

        # Get disqualified players from archive if available
        if tourney.archives and 'rounds' in tourney.archives:
            round_key = str(r)
            if round_key in tourney.archives['rounds']:
                round_archive = tourney.archives['rounds'][round_key]

                if 'disqualifiedPlayers' in round_archive:
                    from app.models.tournament import PunishmentType
                    # Find if disqualified players exist
                    for disq_player_data in round_archive['disqualifiedPlayers']:
                        player_name = disq_player_data.get('player', 'Unknown')
                        punishments = disq_player_data.get('punishments', [])

                        # Format punishments
                        formatted_punishments = []
                        for p in punishments:
                            try:
                                punishment_type = PunishmentType[p.get('type').upper()]
                                reason = punishment_type.past_tense
                            except KeyError:
                                current_app.logger.error(
                                    "Unknown punishment type provided: %s\nDataset: %s",
                                    p.get('type', 'UNKNOWN'), p
                                )
                                punishment_type = PunishmentType.BAN # default to ban in the case of errors
                                reason = "unknown punishment"

                            issued_at = p.get('issued_at')
                            end_at = p.get('end_at')

                            # Determine reason for disqualification
                            # Determine reason for disqualification
                            start = tourney.start_unix
                            lookback = punishment_type.lookback_seconds
                            lookback_days = lookback // (24 * 60 * 60) # 24h

                            if not end_at or not start:
                                # Missing timestamps, assume qualified
                                current_app.logger.error(
                                    "Timestamps not returned for punishment %s: %s",
                                    p.get('id', 'UNKNOWN'), # punishment id
                                    p # full punishment data
                                )
                                continue
                            elif end_at >= start:
                                # Punishment active during tournament
                                reason = f"{reason} during tournament"
                            elif end_at >= start - lookback:
                                # Before tournament but within lookback window
                                reason = f"{reason} before tournament (within {lookback_days}d lookback)"
                            else:
                                # Before tournament, outside lookback
                                reason = f"{reason} before tournament"

                            # Format dates
                            issued_date = datetime.fromtimestamp(issued_at, UTC).strftime('%Y-%m-%d') if issued_at else 'Unknown'
                            end_date = datetime.fromtimestamp(end_at, UTC).strftime('%Y-%m-%d') if end_at else 'Unknown'

                            formatted_punishments.append({
                                'type': punishment_type.name,
                                'issued_date': issued_date,
                                'end_date': end_date,
                                'reason': reason
                            })

                        # Aggregate player disqualifications
                        if player_name not in all_disqualified_players:
                            all_disqualified_players[player_name] = []

                        all_disqualified_players[player_name].append({
                            'round': r,
                            'punishments': formatted_punishments
                        })

        round_leaderboards.append(round_data)

    kwargs.update({
        'form': form,
        'leaderboard_overall': tourney.get_leaderboard(round_num=None),
        'current_round': current_round,
        'round_leaderboards': round_leaderboards,
        'all_disqualified_players': all_disqualified_players,
        'selected_round': current_round or (round_numbers[-1] if round_numbers else None),
        'cache_stats_locked': tourney.is_archived(),
        'epoch_details': {
            'start_gmt': start_dt.strftime('%a, %d %b %Y %H:%M:%S GMT'),
            'end_gmt': end_dt.strftime('%a, %d %b %Y %H:%M:%S GMT'),
            'start_local_title': f"Local: {start_dt.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}",
            'end_local_title': f"Local: {end_dt.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}",
            'start_relative_title': f"Relative: {_relative_logic(tourney.start_unix, now_ts)}",
            'end_relative_title': f"Relative: {_relative_logic(tourney.end_unix, now_ts)}",
        }
    })

    return render_template('tournament_detail.html', **kwargs)

def _relative_logic(ts, now_ts):
    diff = ts - now_ts
    abs_diff = abs(diff)
    if abs_diff < 60: amount, unit = abs_diff, 's'
    elif abs_diff < 3600: amount, unit = abs_diff // 60, 'm'
    elif abs_diff < 86400: amount, unit = abs_diff // 3600, 'h'
    else: amount, unit = abs_diff // 86400, 'd'
    return 'now' if diff == 0 else (f'in {amount}{unit}' if diff > 0 else f'{amount}{unit} ago')

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
    round_hours_display = int(round_hours) if float(round_hours).is_integer() else round_hours
    message_content = (
        f"# :mega: {tourney.name} Announcement\n\n"
        f"This tournament will start on <t:{tourney.start_unix}:F> and will conclude on <t:{tourney.end_unix}:F>.\n"
        f"It will finish <t:{tourney.end_unix}:R>.\n\n"
        f"**Each round will last {round_hours_display} hour{'' if round_hours_display == 1 else 's'}.**"
    )

    if message:
        message_content += f"\n### Additional Info\n{message}"

    message_content += (
        "\nTo participate, simply play the game as you normally would during the tournament period."
        "\nYour kills are automatically counted and tracked at https://ngmc.co/tournament."
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
            "\n-# Overall Ranking rewards the top 3 players across all rounds. Overall Ranking prizes are cumulative with Per-Round Rewards."
        )
    if any(prizes.get(key) for key in ['round_first', 'round_second', 'round_third']):
        message_content += (
            "\n## :gift: Per-Round Prizes\n"
            f"{format_prize_lines({
                'first': prizes.get('round_first', 'TBA'),
                'second': prizes.get('round_second', 'TBA'),
                'third': prizes.get('round_third', 'TBA'),
            })}"
            "\n-# Titan Rank rewards are not transferable. Per-round Titan Rank rewards are non-cumulative; however, overall ranking players will receive their overall-ranking Titan prize on top of their round-ranking Titan prize (if applicable)."
            "\n\n We wish you all the best! Please note that tournament rules and prizes are subject to change. Frequent updates will be posted to <#1466960479485296640>, along with <@&1081345603268792410> pings."
        )

    try:
        ok = discord_send(
            location=ChannelWebhookUrl.ANNOUNCEMENT_WEBHOOK_URL,
            content=message_content,
        )
        if ok:
            tourney.tournament_info_discord_status = True
            from app import db
            db.session.commit()
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
            f"### Round {round_num}\n{format_placement_lines(entries)}"
        )

    rounds_text = "\n\n".join(round_sections)

    optional_message = (tourney.tournament_info_discord_message or '').strip()

    message = (
        f"# :mega: {tourney.name} Rewards!\n\n"
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
        f"-# <@&1081345603268792410> All prizes have now been distributed. Additions are awarded to accounts automatically. Thank you for participating in the {tourney.name}!\n\n"

        "### Per-Round Prizes\n"
        f"{format_prize_lines(round_prizes)}\n\n"
        "### Overall Prizes\n"
        f"{format_prize_lines(overall_prizes)}"
    )

    try:
        ok = discord_send(
            location=ChannelWebhookUrl.ANNOUNCEMENT_WEBHOOK_URL,
            content=message
        )
        if ok:
            tourney.awards_distributed = True
            from app import db
            db.session.commit()
            flash('Prize announcement sent', 'success')
        else:
            flash('Failed to send Discord message')
    except Exception:
        flash('Error sending Discord message. Please contact an administrator.', 'error')

    return redirect(url_for('main.tournament_editor', tournament_id=tourney.id))

@main_bp.route('/scheduler/<int:tournament_id>/cache/stats', methods=['POST'])
@login_required
def tournament_cache_stats(tournament_id: int):
    tourney = Tournament.query.get_or_404(tournament_id)
    current_app.logger.info(
        "Cache stats requested for tournament id=%s name=%s round_count=%s archived_rounds=%s",
        tourney.id,
        tourney.name,
        tourney.round_count,
        sorted((tourney.archives or {}).get('rounds', {}).keys()) if isinstance(tourney.archives, dict) else [],
    )

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
    current_app.logger.debug(
        "Cache stats before archive attempt for tournament id=%s: round_keys=%s",
        tourney.id,
        sorted(before_rounds),
    )

    try:
        failures = list(tourney.archive_stats())
        current_app.logger.info(
            "Archive generator completed for tournament id=%s with results=%s",
            tourney.id,
            failures,
        )
        failed_rounds = sorted(round_num for round_num, ok in failures if ok is False)

        # Refresh to get updated archive data
        from app import db
        db.session.refresh(tourney)

        after_rounds = _round_keys()
        current_app.logger.debug(
            "Cache stats after archive attempt for tournament id=%s: round_keys=%s",
            tourney.id,
            sorted(after_rounds),
        )
        cached_rounds = sorted(after_rounds - before_rounds)

        if cached_rounds:
            message = f"Successfully cached {_format_rounds(cached_rounds)}"
            current_app.logger.info(
                "Cache stats success for tournament id=%s: cached_rounds=%s failed_rounds=%s",
                tourney.id,
                cached_rounds,
                failed_rounds,
            )
            if is_ajax:
                return jsonify({'success': True, 'message': message, 'cached_rounds': cached_rounds, 'failed_rounds': failed_rounds})
            flash(message, 'success')
        elif failed_rounds:
            message = f"Failed to cache {_format_rounds(failed_rounds)}"
            current_app.logger.error(
                "Cache stats failure for tournament id=%s: failed_rounds=%s before_rounds=%s after_rounds=%s",
                tourney.id,
                failed_rounds,
                sorted(before_rounds),
                sorted(after_rounds),
            )
            if is_ajax:
                return jsonify({'success': False, 'message': message, 'cached_rounds': [], 'failed_rounds': failed_rounds}), 500
            flash(message, 'error')
        else:
            message = 'No finished rounds available to cache.'
            current_app.logger.error(
                "Cache stats found no finished rounds for tournament id=%s: before_rounds=%s after_rounds=%s round_count=%s current_round=%s is_active=%s is_expired=%s",
                tourney.id,
                sorted(before_rounds),
                sorted(after_rounds),
                tourney.round_count,
                getattr(tourney, 'current_round', None),
                tourney.is_active,
                tourney.is_expired,
            )
            if is_ajax:
                return jsonify({'success': False, 'message': message, 'cached_rounds': [], 'failed_rounds': []}), 400
            flash(message, 'error')
    except TournamentArchiveException as exc:
        current_app.logger.error(
            "TournamentArchiveException while caching tournament id=%s: %s",
            tourney.id,
            exc,
        )
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

@main_bp.route('/scheduler/<int:tournament_id>/delete', methods=['POST'])
@login_required
def tournament_delete(tournament_id: int):
    from app import db
    if not current_user.is_manager():
        flash('Access denied: Managers only.', 'error')
        return redirect(url_for('main.tournament_editor', tournament_id=tournament_id)), 403

    tourney = Tournament.query.get_or_404(tournament_id)

    password = (request.form.get('confirm_password') or '').strip()
    if not password:
        flash('Please enter your password to confirm deletion.', 'error')
        return redirect(url_for('main.tournament_editor', tournament_id=tourney.id))

    # Verify current user's password
    try:
        if not current_user.check_password(password):
            flash('Password incorrect. Tournament not deleted.', 'error')
            return redirect(url_for('main.tournament_editor', tournament_id=tourney.id))
    except Exception:
        flash('Error verifying password. Tournament not deleted.', 'error')
        return redirect(url_for('main.tournament_editor', tournament_id=tourney.id))

    # Perform deletion
    try:
        db.session.delete(tourney)
        db.session.commit()
        current_app.logger.info('Tournament id=%s name=%s deleted by user id=%s', tourney.id, tourney.name, current_user.id)
        flash(f'Tournament "{tourney.name}" deleted.', 'success')
        return redirect(url_for('main.scheduler'))
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Failed to delete tournament id=%s', tourney.id)
        flash('Failed to delete tournament. Please contact an administrator.', 'error')
        return redirect(url_for('main.tournament_editor', tournament_id=tourney.id))
