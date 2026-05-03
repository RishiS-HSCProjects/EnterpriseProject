from datetime import datetime, UTC
from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField, PasswordField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, EqualTo, NumberRange, Regexp, ValidationError
class LoginForm(FlaskForm):
    """Form for user login."""
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Log In')

class RegistrationForm(FlaskForm):
    """Form for user registration."""
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    password_confirm = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Register')

class VerificationPinForm(FlaskForm):
    """Form for PIN verification after registration."""
    pin = StringField(
        'Verification PIN',
        validators=[
            DataRequired(),
            Regexp(r'^\d{6}$', message='PIN must be exactly 6 digits.')
        ]
    )
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Verify PIN')

class AddTournamentForm(FlaskForm):
    """Form for adding a new tournament."""
    name = StringField('Tournament Name', validators=[DataRequired(), Length(min=3, max=100)])
    start_unix = IntegerField('Start (Unix epoch seconds)', validators=[DataRequired()])
    end_unix = IntegerField('End (Unix epoch seconds)', validators=[DataRequired()])
    round_count = IntegerField('Number of Rounds', validators=[DataRequired(), NumberRange(min=1)])
    discord_message = TextAreaField('Tournament Info Discord Message (optional)', validators=[Length(max=2000)])
    submit = SubmitField('Create Tournament')

    def validate_start_unix(self, field):
        if self.end_unix.data and field.data >= self.end_unix.data:
            raise ValidationError('Start time must be before end time')

        from app.models import Tournament
        if tourney := (Tournament.query.filter(
            Tournament.start_unix < self.end_unix.data
        ).first()):
            raise ValidationError(f'Time overlap: This tournament starts before the {tourney.name} ends (unix {tourney.end_unix}).')


    def validate_end_unix(self, field):
        if self.start_unix.data and field.data and field.data <= self.start_unix.data:
            raise ValidationError('End time must be after start time')

        from app.models import Tournament
        if tourney := (Tournament.query.filter(
            Tournament.end_unix > self.start_unix.data
        ).first()):
            raise ValidationError(f'Time overlap: This tournament ends after the {tourney.name} starts (unix {tourney.start_unix}).')

    def validate_round_count(self, field):
        if field.data < 1:
            raise ValidationError('Round count must be at least 1')
        
        if self.start_unix.data and self.end_unix.data:
            total_duration = (self.end_unix.data - self.start_unix.data)
            round_duration = total_duration / field.data
            if round_duration < 1800: # 30 mins
                raise ValidationError('Round duration must be at least 30 minutes. Please increase the time range or reduce the number of rounds.')

    def validate_discord_message(self, field):
        if field.data and len(field.data) > 2000:
            raise ValidationError('Discord message cannot exceed 2000 characters.')
