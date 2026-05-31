from dataclasses import dataclass
from datetime import datetime, UTC
from enum import Enum, auto
from flask import current_app
from sqlalchemy.ext.mutable import MutableDict
from app import db

class PunishmentType(Enum):
    """Punishment types that can disqualify a player."""
    BAN = auto()
    MUTE = auto()

    @property
    def lookback_seconds(self) -> int:
        if self == PunishmentType.BAN:
            return 30 * 24 * 60 * 60 # 30d
        if self == PunishmentType.MUTE:
            return 7 * 24 * 60 * 60 # 7d
        raise ValueError(self)

    @property
    def past_tense(self) -> str:
        if self == PunishmentType.BAN:
            return 'banned'
        if self == PunishmentType.MUTE:
            return 'muted'
        raise ValueError(self)

@dataclass
class ArchivedPunishment:
    """Minimal punishment snapshot stored inside the archive."""
    id: str | None
    issued_at: int
    end_at: int | None
    type: PunishmentType

    def to_dict(self):
        return {
            'id': self.id,
            'issued_at': self.issued_at,
            'end_at': self.end_at,
            'type': self.type.name,
        }

@dataclass
class NormalizedPunishment:
    """Internal normalized shape used by archive filtering logic."""
    id: str | None
    type: PunishmentType
    issued_at: int
    valid_until: int | None
    player: str

@dataclass
class DisqualifiedPlayerArchive:
    """Archive entry for a player who should not appear in winners."""
    player: str
    punishments: list[ArchivedPunishment]

    def to_dict(self):
        return {
            'player': self.player,
            'punishments': [punishment.to_dict() for punishment in self.punishments],
        }

def _round_entries(round_data):
    """Return the raw entry container from an archived round payload."""
    if not isinstance(round_data, dict):
        return []

    return round_data.get('entries') or []

def _leaderboard_entries(round_data, excluded_players: set[str] | None = None) -> list['LeaderboardEntry']:
    excluded_players = excluded_players or set()
    raw_entries = _round_entries(round_data)

    iterable = raw_entries if isinstance(raw_entries, list) else []

    entries: list[LeaderboardEntry] = []
    for entry in iterable:
        if not isinstance(entry, dict):
            continue

        player = entry.get('player')
        if not isinstance(player, str) or not player or player in excluded_players:
            continue

        score = entry.get('score') or entry.get('value', 0)
        entries.append(LeaderboardEntry(player, score))

    return entries


def format_punishments_for_ui(punishments, tournament_start: int) -> list[dict[str, str]]:
    """Format archived punishment dicts for display in templates.

    Accepts punishment records with keys like `type`, `issued_at` and `end_at` (as
    produced by `_archive_punishment`) and returns a list of simple dicts with
    human-friendly dates and a `reason` string.
    """
    formatted_punishments: list[dict[str, str]] = []
    for punishment in punishments:
        try:
            punishment_type = PunishmentType[str((punishment.get('type') or '').upper())]
            reason = punishment_type.past_tense
        except Exception:
            current_app.logger.error(
                "Unknown punishment type provided: %s\nDataset: %s",
                punishment.get('type', 'UNKNOWN'),
                punishment,
            )
            punishment_type = PunishmentType.BAN
            reason = 'unknown punishment'

        issued_at = punishment.get('issued_at') or punishment.get('issuedAt')
        end_at = punishment.get('end_at') or punishment.get('endAt')
        lookback = punishment_type.lookback_seconds
        lookback_days = lookback // (24 * 60 * 60)

        if not end_at or not tournament_start:
            current_app.logger.error(
                "Timestamps not returned for punishment %s: %s",
                punishment.get('id', 'UNKNOWN'),
                punishment,
            )
            continue
        if end_at >= tournament_start:
            reason = f"{reason} during tournament"
        elif end_at >= tournament_start - lookback:
            reason = f"{reason} before tournament (within {lookback_days}d lookback)"
        else:
            reason = f"{reason} before tournament"

        formatted_punishments.append({
            'type': punishment_type.name,
            'issued_date': datetime.fromtimestamp(issued_at, UTC).strftime('%Y-%m-%d') if issued_at else 'Unknown',
            'end_date': datetime.fromtimestamp(end_at, UTC).strftime('%Y-%m-%d') if end_at else 'Unknown',
            'reason': reason,
        })

    return formatted_punishments

def _store_round_archive(archive_data):
    # Always save the round in one shape so leaderboard reads stay simple.
    if isinstance(archive_data, dict):
        entries = list(archive_data.values())
    elif isinstance(archive_data, list):
        entries = archive_data
    else:
        entries = []

    return {
        'entries': entries,
    }

class AggregationMethod(Enum):
    """Leaderboard aggregation strategies."""
    SUM = 'sum'              # Total score across all rounds
    BEST_RANK = 'best_rank'  # Best placement rank

class RewardPackageTypes(Enum):
    """Supported reward packaging targets."""
    # Highest placements in individual rounds
    ROUND_FIRSTS = 'round_firsts'
    ROUND_SECONDS = 'round_seconds'
    ROUND_THIRDS = 'round_thirds'

    # All players who achieved a specific placement in any round
    ALL_FIRSTS = 'all_firsts'
    ALL_SECONDS = 'all_seconds'
    ALL_THIRDS = 'all_thirds'

    # Overall tournament placements
    GLOBAL_FIRST = 'global_first'
    GLOBAL_SECOND = 'global_second'
    GLOBAL_THIRD = 'global_third'

@dataclass
class LeaderboardEntry:
    """Single leaderboard entry: player and their score."""
    player: str
    score: int
    rank: int | None = None

class RoundLeaderboard:
    """Leaderboard for a single round."""
    def __init__(self, round_num: int, entries: list[LeaderboardEntry]):
        self.round_num = round_num
        self.entries = sorted(entries, key=lambda e: e.score, reverse=True)

    def get_top(self, limit: int = 10) -> list[LeaderboardEntry]:
        """Get top N entries."""
        return self.entries[:limit]

class TournamentLeaderboard:
    """Overall tournament leaderboard with aggregation."""
    def __init__(self, tournament: 'Tournament'):
        self.tournament = tournament
        self._entries_cache: dict[str, int] = {}
        self._best_ranks: dict[str, int] = {}
        self._loaded = False

    def _load(self):
        """Load archived rounds once and cache the combined leaderboard."""
        if self._loaded:
            return

        excluded_players = self.tournament.validated_disqualified_players()
        archives = self.tournament.archives or {}
        rounds_data = archives.get('rounds') if isinstance(archives, dict) else {}

        if isinstance(rounds_data, dict):
            for round_data in rounds_data.values():
                for entry in _leaderboard_entries(round_data, excluded_players=excluded_players):
                    self._entries_cache[entry.player] = self._entries_cache.get(entry.player, 0) + entry.score

        placements = archives.get('placements') if isinstance(archives, dict) else None
        if isinstance(placements, dict):
            for place_str, placement_list in placements.items():
                rank = int(place_str)
                for entry in placement_list or []:
                    player = entry.get('player') if isinstance(entry, dict) else None
                    if player and player not in excluded_players and player not in self._best_ranks:
                        self._best_ranks[player] = rank

        reward_packages = archives.get('rewardPackages') if isinstance(archives, dict) else None
        round_best = reward_packages.get('round_best') if isinstance(reward_packages, dict) else None
        if isinstance(round_best, dict):
            for cached_entry in round_best.values():
                if not isinstance(cached_entry, dict):
                    continue
                player = cached_entry.get('player')
                rank = cached_entry.get('rank')
                if not isinstance(player, str) or not player or player in excluded_players or not isinstance(rank, int):
                    continue
                current_rank = self._best_ranks.get(player)
                if current_rank is None or rank < current_rank:
                    self._best_ranks[player] = rank

        self._loaded = True

    def get_entries(self, method: AggregationMethod = AggregationMethod.SUM, limit: int | None = None) -> list[LeaderboardEntry]:
        """Get aggregated entries by method."""
        self._load()

        if method == AggregationMethod.SUM:
            entries = [LeaderboardEntry(player, score) for player, score in self._entries_cache.items()]
            entries.sort(key=lambda e: e.score, reverse=True)
        else:
            entries = [LeaderboardEntry(player, rank, rank=rank) for player, rank in self._best_ranks.items()]
            entries.sort(key=lambda e: e.rank or 0)

        return entries[:limit] if limit else entries

@dataclass
class TournamentPrizes:
    """Data class representing tournament prizes."""
    overall_first: str = ""
    overall_second: str = ""
    overall_third: str = ""
    round_first: str = ""
    round_second: str = ""
    round_third: str = ""

    def to_dict(self):
        return {
            'overall_first': self.overall_first,
            'overall_second': self.overall_second,
            'overall_third': self.overall_third,
            'round_first': self.round_first,
            'round_second': self.round_second,
            'round_third': self.round_third,
        }

    def from_dict(self, data: dict) -> 'TournamentPrizes':
        return TournamentPrizes(
            data.get('overall_first', ""),
            data.get('overall_second', ""),
            data.get('overall_third', ""),
            data.get('round_first', ""),
            data.get('round_second', ""),
            data.get('round_third', "")
        )

class Tournament(db.Model):
    """Model representing a tournament."""
    __tablename__ = 'tournaments'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    start_unix = db.Column(db.Integer, nullable=False)
    end_unix = db.Column(db.Integer, nullable=False)
    round_count = db.Column(db.Integer, nullable=False, default=7)
    tournament_info_discord_message = db.Column(db.String(2000), nullable=True)
    tournament_info_discord_status = db.Column(db.Boolean, nullable=False, default=False)
    prizes = db.Column(MutableDict.as_mutable(db.JSON), default=dict)
    awards_distributed = db.Column(db.Boolean, nullable=False, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_by_xuid = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.Integer, nullable=False, default=lambda: int(datetime.now(UTC).timestamp()))
    updated_at = db.Column(db.Integer, nullable=False, default=lambda: int(datetime.now(UTC).timestamp()), onupdate=lambda: int(datetime.now(UTC).timestamp()))
    archives = db.Column(MutableDict.as_mutable(db.JSON), default=dict)

    def __repr__(self):
        return f'<Tournament {self.name} from {self.start_unix} to {self.end_unix}>'

    @property
    def round_duration(self):
        """Duration of a single round in seconds."""
        return (self.end_unix - self.start_unix) / self.round_count

    @property
    def start_datetime(self):
        return datetime.fromtimestamp(self.start_unix, UTC)

    @property
    def end_datetime(self):
        return datetime.fromtimestamp(self.end_unix, UTC)

    @property
    def is_upcoming(self):
        now = int(datetime.now(UTC).timestamp())
        return now < self.start_unix

    @property
    def is_active(self):
        now = int(datetime.now(UTC).timestamp())
        return self.start_unix <= now <= self.end_unix

    @property
    def is_expired(self):
        now = int(datetime.now(UTC).timestamp())
        return now > self.end_unix

    @property
    def recipients_validated(self) -> bool:
        """Return whether recipient validation has already completed."""
        archives = self.archives or {}
        if not isinstance(archives, dict):
            return False

        return bool(archives.get('recipients_validated', False))

    def _validation_registry(self) -> dict:
        """Return the persisted validation payload, if it exists."""
        archives = self.archives or {}
        if not isinstance(archives, dict):
            return {}

        validation = archives.get('validation')
        return validation if isinstance(validation, dict) else {}

    def _validated_recipients(self) -> dict[str, list[dict[str, object]] | dict[str, dict[str, object]]]:
        """Return the saved recipient validation payload grouped by reward scope."""
        validation = self._validation_registry()
        recipients = validation.get('recipients')
        return recipients if isinstance(recipients, dict) else {}

    def validated_disqualified_players(self) -> set[str]:
        """Return the set of players rejected by recipient validation."""
        validation = self._validation_registry()
        disqualified_players = validation.get('disqualifiedPlayers') or []

        players: set[str] = set()
        if isinstance(disqualified_players, list):
            for entry in disqualified_players:
                if not isinstance(entry, dict):
                    continue
                player = entry.get('player')
                if isinstance(player, str) and player:
                    players.add(player)

        return players

    @recipients_validated.setter
    def recipients_validated(self, value: bool) -> None:
        """Persist the recipient validation flag inside the archives JSON."""
        archives = self.archives or {}
        if not isinstance(archives, dict):
            archives = {}

        archives['recipients_validated'] = bool(value)
        self.archives = archives

    def get_round_status(self, round_number: int) -> bool:
        """Checks if a specific round has finished."""
        if type(round_number) != int or round_number < 1 or round_number > self.round_count:
            raise ValueError(
                f"Round number must be an integer between 1 and {self.round_count}, {round_number} of type {type(round_number)} given."
            )

        round_end_time = self.start_unix + int(round_number * self.round_duration)
        return int(datetime.now(UTC).timestamp()) > round_end_time

    def is_archived(self):
        """Check if all possible rounds have been archived with actual data."""
        rounds_data = self._get_rounds_data()
        if len(rounds_data) < self.round_count:
            return False
        # Verify each round actually has entries (not just a key)
        for round_num in range(1, self.round_count + 1):
            round_key = str(round_num)
            if round_key not in rounds_data:
                return False
            round_archive = rounds_data[round_key]
            if not isinstance(round_archive, dict) or 'entries' not in round_archive:
                return False
        return True

    def _get_rounds_data(self) -> dict:
        """Return round archives keyed by 1-based round number as strings."""
        archives = self.archives or {}
        if not isinstance(archives, dict):
            archives = {}

        rounds_data = archives.get('rounds')
        if isinstance(rounds_data, dict):
            return rounds_data

        archives['rounds'] = {}
        self.archives = archives
        return archives['rounds']

    def _resolve_player_xuid(self, player: str) -> str | None:
        """Resolve a player name to an XUID, preferring the local user record."""
        from app.models.user import User

        user = User.query.filter_by(username=player).first()
        if user and user.xuid:
            return str(user.xuid)

        try:
            player_data = User.get_player_data(player)
        except Exception as exc:
            current_app.logger.debug("Unable to resolve XUID for player %s: %s", player, exc)
            return None

        xuid = str(player_data.get('xuid') or '')
        return xuid or None

    def _reward_package_cache(self) -> dict:
        """Return the archive section that stores packaged reward candidates."""
        archives = self.archives or {}
        if not isinstance(archives, dict):
            archives = {}

        reward_packages = archives.get('rewardPackages')
        if not isinstance(reward_packages, dict):
            reward_packages = {}
            archives['rewardPackages'] = reward_packages
            self.archives = archives

        return reward_packages

    def _update_reward_package_cache(self, round_num: int, round_data: dict) -> None:
        """Persist the best per-round placements by XUID while archiving a round."""
        reward_packages = self._reward_package_cache()
        round_best = reward_packages.get('round_best')
        if not isinstance(round_best, dict):
            round_best = {}

        all_winners = reward_packages.get('all_winners')
        if not isinstance(all_winners, dict):
            all_winners = {}

        round_entries = sorted(
            _leaderboard_entries(round_data),
            key=lambda entry: entry.score,
            reverse=True,
        )[:3]

        for rank, entry in enumerate(round_entries, start=1):
            xuid = self._resolve_player_xuid(entry.player)
            if not xuid:
                continue

            current_entry = round_best.get(xuid)
            current_rank = current_entry.get('rank') if isinstance(current_entry, dict) else None
            current_round = current_entry.get('round') if isinstance(current_entry, dict) else None
            if current_rank is None or rank < current_rank or (rank == current_rank and (current_round is None or round_num < current_round)):
                round_best[xuid] = {
                    'player': entry.player,
                    'xuid': xuid,
                    'rank': rank,
                    'round': round_num,
                    'score': entry.score,
                }

            rank_key = str(rank)
            rank_entries = all_winners.get(rank_key)
            if not isinstance(rank_entries, list):
                rank_entries = []
            rank_entries.append({
                'player': entry.player,
                'xuid': xuid,
                'rank': rank,
                'round': round_num,
                'score': entry.score,
            })
            all_winners[rank_key] = rank_entries

        reward_packages['round_best'] = round_best
        reward_packages['all_winners'] = all_winners
        archives = self.archives or {}
        if not isinstance(archives, dict):
            archives = {}
        archives['rewardPackages'] = reward_packages
        self.archives = archives

    def _legacy_round_reward_entries(self, target_rank: int) -> list[dict[str, object]]:
        """Backfill round reward entries from archived rounds when cache data is missing."""
        round_entries: list[dict[str, object]] = []
        reward_packages = self._reward_package_cache()
        round_best = reward_packages.get('round_best') if isinstance(reward_packages, dict) else {}
        if isinstance(round_best, dict):
            for entry in round_best.values():
                if not isinstance(entry, dict) or entry.get('rank') != target_rank:
                    continue

                xuid = str(entry.get('xuid') or '')
                if not xuid:
                    player = entry.get('player')
                    if isinstance(player, str) and player:
                        xuid = self._resolve_player_xuid(player) or ''
                if not xuid:
                    continue

                round_entries.append({
                    'player': entry.get('player', ''),
                    'xuid': xuid,
                    'rank': entry.get('rank', target_rank),
                    'round': entry.get('round'),
                })

        if round_entries:
            round_entries.sort(key=lambda entry: (entry.get('round', 0) or 0, str(entry.get('player', '')).lower()))
            return round_entries

        rounds_data = self._get_rounds_data()
        for round_num in range(1, self.round_count + 1):
            round_data = rounds_data.get(str(round_num)) if isinstance(rounds_data, dict) else None
            if not isinstance(round_data, dict):
                continue

            for entry in sorted(_leaderboard_entries(round_data), key=lambda item: item.score, reverse=True)[:3]:
                if entry.rank != target_rank:
                    continue

                xuid = self._resolve_player_xuid(entry.player)
                if not xuid:
                    continue

                round_entries.append({
                    'player': entry.player,
                    'xuid': xuid,
                    'rank': entry.rank,
                    'round': round_num,
                })

        round_entries.sort(key=lambda entry: (entry.get('round', 0) or 0, str(entry.get('player', '')).lower()))
        return round_entries

    def _legacy_all_reward_entries(self, target_rank: int) -> list[dict[str, object]]:
        """Backfill all reward entries from archived rounds when cache data is missing."""
        reward_packages = self._reward_package_cache()
        all_winners = reward_packages.get('all_winners') if isinstance(reward_packages, dict) else None
        if isinstance(all_winners, dict):
            cached_entries = all_winners.get(str(target_rank))
            if isinstance(cached_entries, list):
                normalized_entries: list[dict[str, object]] = []
                for entry in cached_entries:
                    if not isinstance(entry, dict):
                        continue

                    xuid = str(entry.get('xuid') or '')
                    player = entry.get('player')
                    if not xuid and isinstance(player, str) and player:
                        xuid = self._resolve_player_xuid(player) or ''
                    if not xuid:
                        continue

                    normalized_entries.append({
                        'player': entry.get('player', ''),
                        'xuid': xuid,
                        'rank': entry.get('rank', target_rank),
                        'round': entry.get('round'),
                    })

                if normalized_entries:
                    normalized_entries.sort(key=lambda entry: (entry.get('round', 0) or 0, str(entry.get('player', '')).lower()))
                    return normalized_entries

        legacy_entries: list[dict[str, object]] = []
        rounds_data = self._get_rounds_data()
        for round_num in range(1, self.round_count + 1):
            round_data = rounds_data.get(str(round_num)) if isinstance(rounds_data, dict) else None
            if not isinstance(round_data, dict):
                continue

            for entry in sorted(_leaderboard_entries(round_data), key=lambda item: item.score, reverse=True)[:3]:
                if entry.rank != target_rank:
                    continue

                xuid = self._resolve_player_xuid(entry.player)
                if not xuid:
                    continue

                legacy_entries.append({
                    'player': entry.player,
                    'xuid': xuid,
                    'rank': entry.rank,
                    'round': round_num,
                })

        legacy_entries.sort(key=lambda entry: (entry.get('round', 0) or 0, str(entry.get('player', '')).lower()))
        return legacy_entries

    def get_reward_package(self, reward_type: str) -> dict[str, object]:
        """Package reward recipients for a selected reward type from cached archive data."""
        normalized_reward_type = (reward_type or '').strip().lower()
        reward_type_map = {
            RewardPackageTypes.ROUND_FIRSTS.value: ('round', 1),
            RewardPackageTypes.ROUND_SECONDS.value: ('round', 2),
            RewardPackageTypes.ROUND_THIRDS.value: ('round', 3),
            RewardPackageTypes.ALL_FIRSTS.value: ('all', 1),
            RewardPackageTypes.ALL_SECONDS.value: ('all', 2),
            RewardPackageTypes.ALL_THIRDS.value: ('all', 3),
            RewardPackageTypes.GLOBAL_FIRST.value: ('global', 1),
            RewardPackageTypes.GLOBAL_SECOND.value: ('global', 2),
            RewardPackageTypes.GLOBAL_THIRD.value: ('global', 3),
        }

        if normalized_reward_type not in reward_type_map:
            raise ValueError(f"Unsupported reward type: {reward_type}")

        reward_scope, target_rank = reward_type_map[normalized_reward_type]
        package_entries: list[dict[str, object]] = []
        unresolved_players: list[str] = []
        excluded_players = self.validated_disqualified_players()
        validated_recipients = self._validated_recipients()

        def _normalize_saved_entry(entry: dict | None, default_round: int | None = None) -> dict[str, object] | None:
            if not isinstance(entry, dict):
                return None

            player = entry.get('player')
            xuid = str(entry.get('xuid') or '')
            if not isinstance(player, str) or not player or player in excluded_players or not xuid:
                if isinstance(player, str) and player and not xuid:
                    unresolved_players.append(player)
                return None

            normalized_entry: dict[str, object] = {
                'player': player,
                'xuid': xuid,
                'rank': int(entry.get('rank') or target_rank),
            }

            round_num = entry.get('round', default_round)
            if isinstance(round_num, int):
                normalized_entry['round'] = round_num
            elif default_round is not None:
                normalized_entry['round'] = default_round

            return normalized_entry

        def _round_recipient_key(rank: int) -> str:
            return {1: 'round_firsts', 2: 'round_seconds', 3: 'round_thirds'}.get(rank, 'round_firsts')

        if reward_scope == 'round':
            saved_round_entries = validated_recipients.get(_round_recipient_key(target_rank)) or []
            normalized_entries: list[dict[str, object]] = []

            if isinstance(saved_round_entries, list):
                best_entries_by_player: dict[str, dict[str, object]] = {}
                for entry in saved_round_entries:
                    normalized = _normalize_saved_entry(entry)
                    if not normalized or normalized.get('rank') != target_rank:
                        continue

                    player = str(normalized.get('player') or '')
                    if not player:
                        continue

                    current_entry = best_entries_by_player.get(player)
                    current_round = current_entry.get('round') if isinstance(current_entry, dict) else None
                    new_round = normalized.get('round') if isinstance(normalized.get('round'), int) else None
                    if current_entry is None or not isinstance(current_round, int) or (isinstance(new_round, int) and new_round < current_round):
                        best_entries_by_player[player] = normalized

                normalized_entries = list(best_entries_by_player.values())

            normalized_entries.sort(key=lambda entry: (entry.get('round', 0) or 0, str(entry.get('player', '')).lower()))
            package_entries = normalized_entries
        elif reward_scope == 'all':
            saved_all_entries = validated_recipients.get(_round_recipient_key(target_rank)) or []
            if isinstance(saved_all_entries, list):
                for entry in saved_all_entries:
                    normalized = _normalize_saved_entry(entry)
                    if normalized and normalized.get('rank') == target_rank:
                        package_entries.append(normalized)
        else:
            saved_global_entries = validated_recipients.get('global') or {}
            if isinstance(saved_global_entries, dict):
                selected_entry = saved_global_entries.get({1: 'first', 2: 'second', 3: 'third'}.get(target_rank, ''))
                normalized = _normalize_saved_entry(selected_entry)
                if normalized and normalized.get('rank') == target_rank:
                    package_entries.append(normalized)

        return {
            'reward_type': normalized_reward_type,
            'reward_scope': reward_scope,
            'target_rank': target_rank,
            'entries': package_entries,
            'unresolved_players': unresolved_players,
            'ids': tuple(entry['xuid'] for entry in package_entries if entry.get('xuid')),
        }

    def get_reward_packages(self) -> list[dict[str, object]]:
        """Return all supported reward packages in display order."""
        package_order = [
            (RewardPackageTypes.ROUND_FIRSTS.value, 'Top Rank 1sts'),
            (RewardPackageTypes.ROUND_SECONDS.value, 'Top Rank 2nds'),
            (RewardPackageTypes.ROUND_THIRDS.value, 'Top Rank 3rds'),
            (RewardPackageTypes.ALL_FIRSTS.value, 'All Rank 1sts'),
            (RewardPackageTypes.ALL_SECONDS.value, 'All Rank 2nds'),
            (RewardPackageTypes.ALL_THIRDS.value, 'All Rank 3rds'),
            (RewardPackageTypes.GLOBAL_FIRST.value, 'Global 1st'),
            (RewardPackageTypes.GLOBAL_SECOND.value, 'Global 2nd'),
            (RewardPackageTypes.GLOBAL_THIRD.value, 'Global 3rd'),
        ]

        packages: list[dict[str, object]] = []
        for reward_type, reward_label in package_order:
            package = self.get_reward_package(reward_type)
            raw_ids = package.get('ids')
            raw_unresolved_players = package.get('unresolved_players')
            ids = list(raw_ids) if isinstance(raw_ids, list | tuple) else []
            unresolved_players = list(raw_unresolved_players) if isinstance(raw_unresolved_players, list | tuple) else []
            reward_scope = str(package.get('reward_scope') or '')
            if reward_scope == 'global':
                display_text = ', '.join(ids)
            elif ids:
                display_text = f"{len(ids)} recipient{'s' if len(ids) != 1 else ''}"
            else:
                display_text = 'No recipients'

            packages.append({
                'reward_type': reward_type,
                'reward_label': reward_label,
                'ids': ids,
                'copy_text': str(tuple(ids)),
                'display_text': display_text,
                'reward_scope': reward_scope,
                'unresolved_players': unresolved_players,
            })

        return packages

    def get_leaderboard(self, round_num: int | None = None) -> RoundLeaderboard | TournamentLeaderboard:
        """Get leaderboard for a specific round or the overall tournament."""
        if round_num is not None:
            if round_num < 1 or round_num > self.round_count:
                return RoundLeaderboard(round_num, [])

            round_data = self._get_rounds_data().get(str(round_num))
            return RoundLeaderboard(round_num, _leaderboard_entries(round_data, excluded_players=self.validated_disqualified_players()))

        return TournamentLeaderboard(self)

    def archive_stats(self):
        """Archive only finished rounds that are not already stored."""
        from ..utils.api_utils import request

        updated = False
        rounds_data = self._get_rounds_data()

        current_app.logger.info(
            "Starting archive_stats for tournament id=%s name=%s round_count=%s archived_rounds=%s",
            self.id,
            self.name,
            self.round_count,
            sorted(rounds_data.keys()),
        )

        if self.is_archived():
            current_app.logger.error(
                "Tournament already fully archived before archive_stats ran: tournament id=%s name=%s archived_rounds=%s",
                self.id,
                self.name,
                sorted(rounds_data.keys()),
            )
            raise TournamentArchiveException("Tournament is already fully archived.")

        for round_num in range(1, self.round_count + 1):
            round_key = str(round_num)
            # Skip if already archived with entries or if round isn't finished
            if round_key in rounds_data and isinstance(rounds_data[round_key], dict) and 'entries' in rounds_data[round_key]:
                current_app.logger.debug(
                    "Skipping round %s because archive already contains entries",
                    round_num,
                )
                yield round_num, True
                continue
            round_finished = self.get_round_status(round_num)
            current_app.logger.debug(
                "Round %s archive check: finished=%s round_key_present=%s",
                round_num,
                round_finished,
                round_key in rounds_data,
            )
            if not round_finished:
                current_app.logger.debug(
                    "Skipping round %s because it is not finished yet",
                    round_num,
                )
                continue

            try:
                current_app.logger.debug(
                    "Fetching tournament leaderboard for round %s from NetherGames API",
                    round_num,
                )
                data = request('leaderboard', params={'type': 'tournament', 'round': round_num})
                current_app.logger.debug(
                    "Round %s API payload type=%s keys=%s",
                    round_num,
                    type(data).__name__,
                    list(data.keys())[:10] if isinstance(data, dict) else 'n/a',
                )
                rounds_data[round_key] = _store_round_archive(data)
                self._update_reward_package_cache(round_num, rounds_data[round_key])
                # Reassign the archives mapping to ensure SQLAlchemy detects the in-place
                # mutation of the JSON column and persists it on commit.
                try:
                    archives = self.archives or {}
                    if not isinstance(archives, dict):
                        archives = {}
                    archives['rounds'] = rounds_data
                    self.archives = archives
                except Exception:
                    # If assignment fails for any reason, log and continue; commit may still succeed
                    current_app.logger.exception(
                        "Failed to reassign archives mapping for tournament id=%s after storing round %s",
                        self.id,
                        round_num,
                    )
                current_app.logger.debug(
                    "Stored archive for round %s with %s entries",
                    round_num,
                    len(rounds_data[round_key].get('entries', [])),
                )
                updated = True
                yield round_num, True
            except Exception as exc:
                current_app.logger.exception(
                    "Failed to archive round %s for tournament id=%s name=%s",
                    round_num,
                    self.id,
                    self.name,
                )
                yield round_num, False

        if updated:
            current_app.logger.info(
                "Committing archived tournament data for tournament id=%s name=%s",
                self.id,
                self.name,
            )
            db.session.commit()

    def set_created_by(self, xuid: str, **kwargs):
        """Set the creator of the tournament by their XUID."""
        from app.models.user import User

        user = User.query.filter_by(xuid=xuid).first()
        current_app.logger.info(f"Setting created_by for tournament '{self.name}' to XUID {xuid} (User found: {bool(user)})")
        if user:
            if kwargs.get('delete_user'): self.created_by = None
            else: self.created_by = user.id
        else: raise ValueError(f"No user found with XUID {xuid}")

        self.created_by_xuid = xuid

    @classmethod
    def create(
        cls,
        name: str,
        start_unix: int,
        end_unix: int,
        round_count: int,
        created_by: int,
        tournament_info_discord_message: str | None = None,
        prizes: TournamentPrizes | None = None,
    ) -> 'Tournament':
        """Factory method to create a new tournament using unix timestamps."""
        if start_unix >= end_unix:
            raise ValueError("Start unix time must be before end unix time.")
        if round_count < 1:
            raise ValueError("Round count must be at least 1.")

        tournament = cls()
        tournament.name = name
        tournament.start_unix = int(start_unix)
        tournament.end_unix = int(end_unix)
        tournament.round_count = round_count
        tournament.created_by = created_by
        from app.models.user import User
        tournament.created_by_xuid = user.xuid if (user := User.query.get(created_by)) else None
        message = (tournament_info_discord_message or '').strip()
        tournament.tournament_info_discord_message = message or None
        tournament.prizes = prizes.to_dict() if prizes else {}
        db.session.add(tournament)
        db.session.commit()
        return tournament

class TournamentExceptionBase(Exception):
    """Base exception class for Tournament-related errors."""
    pass

class TournamentArchiveException(TournamentExceptionBase):
    """Exception raised when archiving fails."""
    pass
