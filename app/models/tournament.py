from datetime import datetime, UTC

from flask import current_app
from app import db
from sqlalchemy.ext.mutable import MutableDict
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
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.Integer, nullable=False, default=lambda: int(datetime.now(UTC).timestamp()))
    updated_at = db.Column(db.Integer, nullable=False, default=lambda: int(datetime.now(UTC).timestamp()), onupdate=lambda: int(datetime.now(UTC).timestamp()))
    archives = db.Column(MutableDict.as_mutable(db.JSON), default=dict)
    awards_distributed = db.Column(db.Boolean, nullable=False, default=False)

    def __repr__(self):
        return f'<Tournament {self.name} from {self.start_unix} to {self.end_unix}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'start_unix': self.start_unix,
            'end_unix': self.end_unix,
            'round_count': self.round_count,
            'archives': self.archives
        }

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
        ): raise ValueError(f"Round number must be an integer between 1 and {self.round_count}")
        
        now = int(datetime.now(UTC).timestamp())
        round_end_time = self.start_unix + int(round_number * self.round_duration)
        return now > round_end_time

    def is_archived(self):
        """Check if all possible rounds have been archived."""
        return len(self.archives) >= self.round_count

    def archive_stats(self):
        """Archive only finished and un-archived rounds."""
        from utils.api_utils import request
        now = datetime.now(UTC)
        updated = False

        if self.is_archived():
            # Skip archiving if all rounds are already archived
            raise TournamentArchiveException("Tournament is already fully archived.")

        for round_num in range(self.round_count):
            round_key = str(round_num)

            if round_key in self.archives:
                continue
                
            if not self.get_round_status(round_num):
                continue

            try:
                data = request('leaderboard', params={'type': 'tournament', 'round': round_num})
                self.archives[round_key] = data
                updated = True
            except Exception as e:
                current_app.logger.error(f"Failed to archive round {round_num}: {e}")
                yield round_num, False

        if updated:
            self.last_archived_at = now
            db.session.commit()

    @classmethod
    def create(cls, name: str, start_unix: int, end_unix: int, round_count: int, created_by: int):
        """Factory method to create a new tournament using unix timestamps.

        `start_unix` and `end_unix` are integer UNIX epoch seconds (UTC).
        """
        if start_unix >= end_unix:
            raise ValueError("Start unix time must be before end unix time.")
        if round_count < 1:
            raise ValueError("Round count must be at least 1.")
        
        tournament = cls(
            name=name,
            start_unix=int(start_unix),
            end_unix=int(end_unix),
            round_count=round_count,
            created_by=created_by
        )
        db.session.add(tournament)
        db.session.commit()
        return tournament

class TournamentExceptionBase(Exception):
    """Base exception class for Tournament-related errors."""
    pass

class TournamentArchiveException(TournamentExceptionBase):
    """Exception raised when archiving fails."""
    pass
