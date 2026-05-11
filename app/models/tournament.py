from dataclasses import dataclass
from datetime import datetime, UTC
from enum import Enum
from sqlalchemy.ext.mutable import MutableDict
from flask import current_app
from app import db


class AggregationMethod(Enum):
    """Leaderboard aggregation strategies."""
    SUM = 'sum'              # Total score across all rounds
    BEST_RANK = 'best_rank'  # Best placement rank


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
        self._entries_cache: dict[str, int] = {}  # player -> total score
        self._best_ranks: dict[str, int] = {}     # player -> best placement rank
        self._loaded = False
    
    def _load(self):
        """Load and aggregate data from archives (lazy load)."""
        if self._loaded:
            return
        
        archives = self.tournament.archives or {}
        
        # Aggregate scores from all rounds
        if 'rounds' in archives:
            rounds_data = archives['rounds']
            if isinstance(rounds_data, dict):
                for round_data in rounds_data.values():
                    self._aggregate_round(round_data)
        
        # Track best placements (1st, 2nd, 3rd only)
        if 'placements' in archives:
            placements = archives['placements']
            for place_str, placement_list in placements.items():
                rank = int(place_str)
                for entry in (placement_list or []):
                    player = entry.get('player')
                    if player and player not in self._best_ranks:
                        self._best_ranks[player] = rank
        
        self._loaded = True
    
    def _aggregate_round(self, round_data):
        """Add scores from a single round."""
        if not round_data:
            return
        
        if isinstance(round_data, dict):
            # Format: { player_id: {player, value} }
            for entry in round_data.values():
                if isinstance(entry, dict):
                    player = entry.get('player')
                    score = entry.get('value') or entry.get('score', 0)
                    if player:
                        self._entries_cache[player] = self._entries_cache.get(player, 0) + score
        elif isinstance(round_data, list):
            # Format: [ {player, score} ]
            for entry in round_data:
                if isinstance(entry, dict):
                    player = entry.get('player')
                    score = entry.get('score') or entry.get('value', 0)
                    if player:
                        self._entries_cache[player] = self._entries_cache.get(player, 0) + score
    
    def get_entries(self, method: AggregationMethod = AggregationMethod.SUM, limit: int | None = None) -> list[LeaderboardEntry]:
        """Get aggregated entries by method.
        
        method: AggregationMethod.SUM or AggregationMethod.BEST_RANK
        limit: max entries to return (None = all)
        """
        self._load()
        
        if method == AggregationMethod.SUM:
            entries = [LeaderboardEntry(p, s) for p, s in self._entries_cache.items()]
            entries.sort(key=lambda e: e.score, reverse=True)
        else:  # BEST_RANK
            entries = [LeaderboardEntry(p, r, rank=r) for p, r in self._best_ranks.items()]
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
    round_count = db.Column(db.Integer, nullable=False, default=7) # >= 1
    tournament_info_discord_message = db.Column(db.String(2000), nullable=True)
    tournament_info_discord_status = db.Column(db.Boolean, nullable=False, default=False)
    prizes = db.Column(MutableDict.as_mutable(db.JSON), default=dict)
    awards_distributed = db.Column(db.Boolean, nullable=False, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.Integer, nullable=False, default=lambda: int(datetime.now(UTC).timestamp()))
    updated_at = db.Column(db.Integer, nullable=False, default=lambda: int(datetime.now(UTC).timestamp()), onupdate=lambda: int(datetime.now(UTC).timestamp()))
    archives = db.Column(MutableDict.as_mutable(db.JSON), default=dict)

    def __repr__(self):
        return f'<Tournament {self.name} from {self.start_unix} to {self.end_unix}>'

    @property
    def round_duration(self):
        """Calculates duration of a single round in seconds."""
        total_duration = self.end_unix - self.start_unix
        return total_duration / self.round_count

    @property
    def start_datetime(self):
        return datetime.fromtimestamp(self.start_unix, UTC)

    @property
    def end_datetime(self):
        return datetime.fromtimestamp(self.end_unix, UTC)

    @property
    def is_upcoming(self):
        """Checks if the tournament is upcoming."""
        now = int(datetime.now(UTC).timestamp())
        return now < self.start_unix

    @property
    def is_active(self):
        """Checks if the tournament is currently active."""
        now = int(datetime.now(UTC).timestamp())
        return self.start_unix <= now <= self.end_unix

    @property
    def is_expired(self):
        """Checks if the tournament has ended."""
        now = int(datetime.now(UTC).timestamp())
        return now > self.end_unix

    def get_round_status(self, round_number: int) -> bool:
        """Checks if a specific round has finished."""

        if (
            type(round_number) != int or
            round_number < 1 or
            round_number > self.round_count
        ): raise ValueError(f"Round number must be an integer between 1 and {self.round_count}, {round_number} of type {type(round_number)} given.")
        
        now = int(datetime.now(UTC).timestamp())
        round_end_time = self.start_unix + int(round_number * self.round_duration)
        return now > round_end_time

    def is_archived(self):
        """Check if all possible rounds have been archived."""
        rounds_data = self._get_rounds_data()
        return len(rounds_data) >= self.round_count

    def _get_rounds_data(self) -> dict:
        """Return round archives keyed by 1-based round number as strings."""
        archives = self.archives or {}
        if not isinstance(archives, dict):
            archives = {}

        rounds_data = archives.get('rounds')
        if isinstance(rounds_data, dict):
            return rounds_data

        # Migrate legacy root-level numeric keys to rounds bucket.
        migrated: dict[str, object] = {}
        for key, value in archives.items():
            key_str = str(key)
            if key_str.isdigit():
                legacy_round = int(key_str)
                normalized_round = legacy_round + 1 if legacy_round == 0 else legacy_round
                migrated[str(normalized_round)] = value

        archives['rounds'] = migrated
        self.archives = archives
        return migrated

    def get_leaderboard(self, round_num: int | None = None) -> RoundLeaderboard | TournamentLeaderboard:
        """Get leaderboard for a specific round or overall tournament.
        
        round_num: Round number (1-indexed). If None, returns overall tournament leaderboard.
        """
        if round_num is not None:
            if round_num < 1 or round_num > self.round_count:
                return RoundLeaderboard(round_num, [])

            rounds_data = self._get_rounds_data()
            round_data = rounds_data.get(str(round_num))
            entries = []
            
            if isinstance(round_data, dict):
                for entry in round_data.values():
                    if isinstance(entry, dict):
                        player = entry.get('player')
                        score = entry.get('value') or entry.get('score', 0)
                        if player:
                            entries.append(LeaderboardEntry(player, score))
            elif isinstance(round_data, list):
                for entry in round_data:
                    if isinstance(entry, dict):
                        player = entry.get('player')
                        score = entry.get('score') or entry.get('value', 0)
                        if player:
                            entries.append(LeaderboardEntry(player, score))
            
            return RoundLeaderboard(round_num, entries)
        
        return TournamentLeaderboard(self)

    def archive_stats(self):
        """Archive only finished and un-archived rounds."""
        from ..utils.api_utils import request
        updated = False
        rounds_data = self._get_rounds_data()

        if self.is_archived():
            # Skip archiving if all rounds are already archived
            raise TournamentArchiveException("Tournament is already fully archived.")

        for round_num in range(1, self.round_count + 1):
            round_key = str(round_num)

            if round_key in rounds_data:
                continue
                
            if not self.get_round_status(round_num):
                continue

            try:
                data = request('leaderboard', params={'type': 'tournament', 'round': round_num})
                rounds_data[round_key] = data
                updated = True
            except Exception as e:
                current_app.logger.error(f"Failed to archive round {round_num}: {e}")
                yield round_num, False

        if updated:
            db.session.commit()

    def set_created_by(self, xuid: str, **kwargs):
        """Set the creator of the tournament by their XUID."""
        from app.models.user import User
        user = User.query.filter_by(xuid=xuid).first()
        current_app.logger.info(f"Setting created_by for tournament '{self.name}' to XUID {xuid} (User found: {bool(user)})")
        if user: self.created_by = user.id
        elif kwargs.get('delete_user'): self.created_by = xuid
        else: raise ValueError(f"No user found with XUID {xuid}")

    @classmethod
    def create(
        cls,
        name: str,
        start_unix: int,
        end_unix: int,
        round_count: int,
        created_by: int,
        prizes: TournamentPrizes | None = None
    ) -> 'Tournament':
        """Factory method to create a new tournament using unix timestamps.

        `start_unix` and `end_unix` are integer UNIX epoch seconds (UTC).
        """
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
