from sqlalchemy import Column, String
from config import Base

class MatchedTrack(Base):
    __tablename__ = "matched_tracks"

    spotify_id = Column(String, primary_key=True, index=True)
    song_name  = Column(String, nullable=False)
    artist     = Column(String, nullable=False)
    album      = Column(String, nullable=True)
    youtube_id = Column(String, nullable=False)

class FailedTrack(Base):
    __tablename__ = "failed_tracks"

    spotify_id = Column(String, primary_key=True, index=True)
    youtube_id = Column(String, nullable=True)
    reason     = Column(String, nullable=True)
