from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

@dataclass
class Show:
    """A podcast or show"""
    id: Optional[int] = None
    name: str = ""
    url: str = ""  # Feed URL
    description: str = ""  # Full show description
    author: str = ""  # Show author/producer
    image_url: str = ""  # Cover image URL
    category: str = ""  # Show category (e.g., "Arts > Design")
    language: str = ""  # Language code (e.g., "en-us")
    copyright: str = ""  # Copyright information
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __str__(self):
        return self.name

@dataclass
class Episode:
    """An episode of a show"""
    id: Optional[int] = None
    show_id: int = None  # Foreign key to Show
    title: str = ""
    url: str = ""  # Direct download URL
    episode_number: str = ""  # Could be "1", "S01E01", etc.
    itunes_episode: str = ""  # iTunes episode number
    description: str = ""  # Full episode description
    summary: str = ""  # Short episode summary
    author: str = ""  # Episode author/host
    image_url: str = ""  # Episode-specific image URL
    duration: str = ""  # Duration in HH:MM:SS format
    keywords: str = ""  # Comma-separated keywords
    published_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    file_hash: Optional[str] = None  # Hash of the downloaded file
    image_file_hash: Optional[str] = None  # Hash of the downloaded image file
    is_downloaded: bool = False      # Whether the episode is currently downloaded
    was_downloaded: bool = False     # Whether the episode was ever downloaded (even if deleted)
    download_date: Optional[datetime] = None  # When the episode was downloaded
    deleted_date: Optional[datetime] = None   # When the downloaded file was deleted
    
    def __str__(self):
        return f"{self.title} ({self.episode_number})" 