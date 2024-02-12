from . import db
from flask_login import UserMixin
from sqlalchemy.sql import func

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    track_id = db.Column(db.String(200))
    name = db.Column(db.String(200))
    artists = db.Column(db.String(500))  # Concatenated string of artists
    danceability = db.Column(db.Float)
    energy = db.Column(db.Float)
    key = db.Column(db.Integer)
    loudness = db.Column(db.Float)
    speechiness = db.Column(db.Float)
    acousticness = db.Column(db.Float)
    instrumentalness = db.Column(db.Float)
    liveness = db.Column(db.Float)
    valence = db.Column(db.Float)
    tempo = db.Column(db.Float)
    duration_ms = db.Column(db.Integer)
    playlist_id = db.Column(db.String(100), nullable=False)  # Ensuring every track is linked to a playlist
    mood = db.Column(db.String(100))  # Store the mood associated with the track
