"""
Configuration utility for Parchive.
Handles loading and validation of the YAML configuration file.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class Config:
    """Configuration manager for Parchive."""
    
    DEFAULT_CONFIG_PATH = "config.yaml"
    _instance = None
    
    def __new__(cls):
        """Singleton pattern to ensure only one config instance exists."""
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._loaded = False
            cls._instance._config = {}
        return cls._instance
    
    def __init__(self):
        """Initialize the configuration manager."""
        if not self._loaded:
            self.load_config()
    
    def load_config(self, config_path: Optional[str] = None) -> None:
        """
        Load configuration from the YAML file.
        
        Args:
            config_path: Optional path to the config file. If not provided,
                         will look for a file at the default location.
        """
        if config_path is None:
            config_path = self.DEFAULT_CONFIG_PATH
        
        path = Path(config_path)
        
        # If config file doesn't exist, use default settings
        if not path.exists():
            self._loaded = True
            self._config = self._get_default_config()
            return
        
        try:
            with open(path, 'r') as f:
                self._config = yaml.safe_load(f)
            self._loaded = True
        except Exception as e:
            print(f"Error loading configuration from {config_path}: {str(e)}")
            print("Using default configuration instead.")
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get the default configuration settings."""
        return {
            "general": {
                "download_directory": "downloads",
                "filename_format": "{episode_number}_{hash}",
                "use_show_id_folders": True,
                "max_parallel_downloads": 3,
                "connect_timeout": 30,
                "read_timeout": 60,
            },
            "database": {
                "path": "app/data/urls.db",
                "backup_before_migration": True,
                "backup_directory": "backups",
                "max_backups": 5,
            },
            "downloads": {
                "download_covers": True,
                "download_episode_images": True,
                "save_feed_xml": True,
                "save_metadata_json": True,
                "max_retries": 3,
                "retry_delay": 5,
                "skip_existing_files": True,
                "preferred_formats": ["mp3", "m4a", "ogg", "aac"],
                "min_audio_quality": 64,
            },
            "ai": {
                "enabled": True,
                "host": "localhost",
                "port": 12434,
                "endpoint": "/engines/v1",
                "show_analysis_model": "llama3-70b",
                "episode_analysis_model": "llama3-70b",
                "max_tokens": 500,
                "stream_responses": False,
                "temperature": 0.7,
            },
            "ui": {
                "use_colors": True,
                "show_progress_bars": True,
                "default_episode_list_limit": 20,
                "show_debug_info": False,
                "confirm_destructive_operations": True,
            },
            "network": {
                "user_agent": "Parchive Podcast Archiver/1.0",
                "use_proxy": False,
                "proxy_url": "",
                "verify_ssl": True,
                "max_redirects": 5,
            },
        }
    
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            section: The configuration section (e.g., 'database', 'ai')
            key: The configuration key within the section
            default: Default value to return if the key is not found
            
        Returns:
            The configuration value, or the default if not found
        """
        if section not in self._config:
            return default
        
        if key not in self._config[section]:
            return default
            
        return self._config[section][key]
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get an entire configuration section.
        
        Args:
            section: The configuration section name
            
        Returns:
            A dictionary of all keys and values in the section,
            or an empty dict if the section doesn't exist
        """
        return self._config.get(section, {})
    
    @property
    def database_path(self) -> str:
        """Get the database path, ensuring the directory exists."""
        db_path = self.get("database", "path", "app/data/urls.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        return db_path
    
    @property
    def download_dir(self) -> str:
        """Get the download directory, ensuring it exists."""
        download_dir = self.get("general", "download_directory", "downloads")
        os.makedirs(download_dir, exist_ok=True)
        return download_dir
    
    @property
    def ai_url(self) -> str:
        """Get the full AI model URL."""
        host = self.get("ai", "host", "localhost")
        port = self.get("ai", "port", 12434)
        endpoint = self.get("ai", "endpoint", "/engines/v1")
        
        # Format the URL properly
        if not host.startswith("http"):
            host = f"http://{host}"
        
        # Ensure endpoint starts with a slash
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
            
        return f"{host}:{port}{endpoint}"
    
    @property
    def ai_enabled(self) -> bool:
        """Check if AI functionality is enabled."""
        return self.get("ai", "enabled", True)


# Create a global instance for import
config = Config() 