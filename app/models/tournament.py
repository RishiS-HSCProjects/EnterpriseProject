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

def _round_disqualified_players(round_data) -> set[str]:
    """Extract disqualified player identifiers already stored for a round."""
    disqualified: set[str] = set()
    if not isinstance(round_data, dict):
        return disqualified

    raw_disqualified = round_data.get('disqualifiedPlayers') or []

    for entry in raw_disqualified:
        if not isinstance(entry, dict):
            continue

        player = entry.get('player')
        if isinstance(player, str) and player:
            disqualified.add(player)

    return disqualified

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

def _punishment_is_disqualifying(punishment: NormalizedPunishment, tournament_start: int) -> bool:
    if punishment.valid_until is None:
        return True

    cutoff = tournament_start - punishment.type.lookback_seconds
    # Disqualify if it lasts into the tournament or ended recently before it.
    return punishment.valid_until >= tournament_start or punishment.valid_until >= cutoff

def _normalize_punishment(punishment: dict) -> NormalizedPunishment | None:
    punishment_type = str(punishment.get('type') or '').upper()
    if punishment_type not in PunishmentType.__members__:
        return None
    punishment_enum = PunishmentType[punishment_type]

    issued_at = punishment.get('issuedAt')
    if not isinstance(issued_at, int):
        return None

    valid_until = punishment.get('validUntil')
    if valid_until is not None and not isinstance(valid_until, int):
        valid_until = None

    player = punishment.get('player')
    if not isinstance(player, str) or not player:
        return None

    return NormalizedPunishment(
        id=punishment.get('id'),
        type=punishment_enum,
        issued_at=issued_at,
        valid_until=valid_until,
        player=player,
    )

def _archive_punishment(punishment: NormalizedPunishment) -> ArchivedPunishment:
    """Store only the punishment fields we actually need later."""
    return ArchivedPunishment(
        id=punishment.id,
        issued_at=punishment.issued_at,
        end_at=punishment.valid_until,
        type=punishment.type,
    )

def _disqualified_players_from_archive(archive_data, tournament_start: int) -> list[dict]:
    punishments = []
    if isinstance(archive_data, dict):
        punishments = archive_data.get('punishmentsNew') or archive_data.get('punishments') or []

    current_app.logger.debug(f"Archive data contains {len(punishments)} raw punishments")

    # Keep the latest BAN and MUTE per player, then apply the time window.
    latest_by_identifier: dict[str, dict[PunishmentType, NormalizedPunishment]] = {}
    for raw_punishment in punishments:
        if not isinstance(raw_punishment, dict):
            continue

        normalized = _normalize_punishment(raw_punishment)
        if not normalized:
            continue

        by_type = latest_by_identifier.setdefault(normalized.player, {})
        current = by_type.get(normalized.type)
        if current is None or normalized.issued_at >= current.issued_at:
            by_type[normalized.type] = normalized

    disqualified: list[dict] = []
    for identifier, punishments_by_type in latest_by_identifier.items():
        punishments: list[ArchivedPunishment] = []
        for punishment in punishments_by_type.values():
            if not _punishment_is_disqualifying(punishment, tournament_start):
                continue

            punishments.append(_archive_punishment(punishment))

        if punishments:
            disqualified.append(DisqualifiedPlayerArchive(identifier, punishments).to_dict())

    current_app.logger.debug(f"Extracted {len(disqualified)} disqualified players from archive")
    return disqualified

def _store_round_archive(archive_data, disqualified_players: list[dict]):
    # Always save the round in one shape so leaderboard reads stay simple.
    if isinstance(archive_data, dict):
        entries = list(archive_data.values())
    elif isinstance(archive_data, list):
        entries = archive_data
    else:
        entries = []

    return {
        'entries': entries,
        'disqualifiedPlayers': disqualified_players,
    }

class AggregationMethod(Enum):
    """Leaderboard aggregation strategies."""
    SUM = 'sum'              # Total score across all rounds
    BEST_RANK = 'best_rank'  # Best placement rank

class RewardPackageTypes(Enum):
    """Supported reward packaging targets."""
    ROUND_FIRSTS = 'round_firsts'
    ROUND_SECONDS = 'round_seconds'
    ROUND_THIRDS = 'round_thirds'
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
        self._disqualified_players: set[str] = set()
        self._loaded = False

    def _load(self):
        """Load archived rounds once and cache the combined leaderboard."""
        if self._loaded:
            return

        archives = self.tournament.archives or {}
        rounds_data = archives.get('rounds') if isinstance(archives, dict) else {}

        if isinstance(rounds_data, dict):
            for round_data in rounds_data.values():
                # Pull archived disqualifications into a fast lookup set.
                self._disqualified_players.update(_round_disqualified_players(round_data))
                for entry in _leaderboard_entries(round_data, self._disqualified_players):
                    self._entries_cache[entry.player] = self._entries_cache.get(entry.player, 0) + entry.score

        placements = archives.get('placements') if isinstance(archives, dict) else None
        if isinstance(placements, dict):
            for place_str, placement_list in placements.items():
                rank = int(place_str)
                for entry in placement_list or []:
                    player = entry.get('player') if isinstance(entry, dict) else None
                    if player and player not in self._best_ranks and player not in self._disqualified_players:
                        self._best_ranks[player] = rank

        reward_packages = archives.get('rewardPackages') if isinstance(archives, dict) else None
        round_best = reward_packages.get('round_best') if isinstance(reward_packages, dict) else None
        if isinstance(round_best, dict):
            for cached_entry in round_best.values():
                if not isinstance(cached_entry, dict):
                    continue
                player = cached_entry.get('player')
                rank = cached_entry.get('rank')
                if not isinstance(player, str) or not player or not isinstance(rank, int):
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

        round_entries = sorted(
            _leaderboard_entries(round_data, _round_disqualified_players(round_data)),
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

        reward_packages['round_best'] = round_best
        archives = self.archives or {}
        if not isinstance(archives, dict):
            archives = {}
        archives['rewardPackages'] = reward_packages
        self.archives = archives

    def get_reward_package(self, reward_type: str) -> dict[str, object]:
        """Package reward recipients for a selected reward type from cached archive data."""
        normalized_reward_type = (reward_type or '').strip().lower()
        reward_type_map = {
            RewardPackageTypes.ROUND_FIRSTS.value: ('round', 1),
            RewardPackageTypes.ROUND_SECONDS.value: ('round', 2),
            RewardPackageTypes.ROUND_THIRDS.value: ('round', 3),
            RewardPackageTypes.GLOBAL_FIRST.value: ('global', 1),
            RewardPackageTypes.GLOBAL_SECOND.value: ('global', 2),
            RewardPackageTypes.GLOBAL_THIRD.value: ('global', 3),
        }

        if normalized_reward_type not in reward_type_map:
            raise ValueError(f"Unsupported reward type: {reward_type}")

        reward_scope, target_rank = reward_type_map[normalized_reward_type]
        package_entries: list[dict[str, object]] = []
        unresolved_players: list[str] = []

        if reward_scope == 'round':
            reward_packages = self._reward_package_cache()
            round_best = reward_packages.get('round_best') if isinstance(reward_packages, dict) else {}
            if not isinstance(round_best, dict):
                round_best = {}

            cached_entries = [
                entry
                for entry in round_best.values()
                if isinstance(entry, dict) and entry.get('rank') == target_rank and isinstance(entry.get('xuid'), str)
            ]
            cached_entries.sort(key=lambda entry: (entry.get('round', 0), str(entry.get('player', '')).lower()))

            for entry in cached_entries:
                package_entries.append({
                    'player': entry.get('player', ''),
                    'xuid': entry.get('xuid', ''),
                    'rank': entry.get('rank', target_rank),
                    'round': entry.get('round'),
                })
        else:
            overall_entries = TournamentLeaderboard(self).get_entries(limit=3)
            if 1 <= target_rank <= len(overall_entries):
                selected_players = [overall_entries[target_rank - 1].player]
            else:
                selected_players = []

            for player in selected_players:
                xuid = self._resolve_player_xuid(player)
                if xuid:
                    package_entries.append({
                        'player': player,
                        'xuid': xuid,
                        'rank': target_rank,
                    })
                else:
                    unresolved_players.append(player)

        return {
            'reward_type': normalized_reward_type,
            'reward_scope': reward_scope,
            'target_rank': target_rank,
            'entries': package_entries,
            'unresolved_players': unresolved_players,
            'ids': tuple(entry['xuid'] for entry in package_entries if entry.get('xuid')),
        }

    def get_reward_packages(self, type=None) -> list[dict[str, object]]:
        """Return all supported reward packages in display order."""
        if type == 'round': package_order = [
                (RewardPackageTypes.ROUND_FIRSTS.value, 'Round 1sts'),
                (RewardPackageTypes.ROUND_SECONDS.value, 'Round 2nds'),
                (RewardPackageTypes.ROUND_THIRDS.value, 'Round 3rds'),
            ]
        elif type == 'global': package_order = [
            (RewardPackageTypes.GLOBAL_FIRST.value, 'Global 1st'),
            (RewardPackageTypes.GLOBAL_SECOND.value, 'Global 2nd'),
            (RewardPackageTypes.GLOBAL_THIRD.value, 'Global 3rd'),
        ]
        else: package_order = [
            (RewardPackageTypes.ROUND_FIRSTS.value, 'Round 1sts'),
            (RewardPackageTypes.ROUND_SECONDS.value, 'Round 2nds'),
            (RewardPackageTypes.ROUND_THIRDS.value, 'Round 3rds'),
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
            return RoundLeaderboard(round_num, _leaderboard_entries(round_data, _round_disqualified_players(round_data)))

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
                # Save the round plus any disqualifications we can infer from the API payload.
                disq_players = _disqualified_players_from_archive(data, self.start_unix)
                current_app.logger.debug(f"Round {round_num}: Found {len(disq_players)} disqualified players")
                rounds_data[round_key] = _store_round_archive(
                    data,
                    disq_players,
                )
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
                    "Stored archive for round %s with %s entries and %s disqualified players",
                    round_num,
                    len(rounds_data[round_key].get('entries', [])),
                    len(rounds_data[round_key].get('disqualifiedPlayers', [])),
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
