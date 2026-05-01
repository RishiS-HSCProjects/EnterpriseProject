from datetime import datetime, UTC

from app import db

class Tournament(db.Model):
    """Model representing a tournament."""
    __tablename__ = 'tournaments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    start_datetime = db.Column(db.DateTime(timezone=True), nullable=False)
    end_datetime = db.Column(db.DateTime(timezone=True), nullable=False)
    round_count = db.Column(db.Integer, nullable=False)
    tournament_info_message = db.Column(db.Text, nullable=True)
    tournament_info_discord_message = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=db.func.now(), onupdate=db.func.now())
    
    def __repr__(self):
        return f'<Tournament {self.name} from {self.start_datetime} to {self.end_datetime}>'
    
    def to_dict(self):
        """Convert tournament to dictionary format."""
        return {
            'id': self.id,
            'name': self.name,
            'start_datetime': self.start_datetime.isoformat(),
            'end_datetime': self.end_datetime.isoformat(),
            'round_count': self.round_count,
            'tournament_info_message': self.tournament_info_message,
            'tournament_info_discord_message': self.tournament_info_discord_message,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def is_active(self):
        """Check if the tournament is currently active."""
        now = datetime.now(UTC)
        return self.start_datetime <= now <= self.end_datetime
    
    def archive_stats(self):
        """Archive the statistics for the tournament."""
        # Pull from API
        pass
    
class TournamentExceptionBase(Exception):
    """Base exception class for Tournament-related errors."""
    pass
