"""Configuration management for NBT viewer."""
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

# Default configuration values
DEFAULT_CONFIG = {
    "nbt_file": "resources/David_0_0.nbt",
    "progress_file": "resources/progress.json",
    "output_directory": "resources/output",
    "backup_directory": "resources/backups",
    "auto_save": True,
    "auto_backup": False,
    "backup_interval": 3600,  # seconds
}

class ConfigManager:
    """Manages application configuration settings."""

    def __init__(self, config_file: Optional[str] = None):
        """Initialize configuration manager.
        
        Args:
            config_file: Path to configuration file. If None, uses default location.
        """
        self.config_file = config_file or os.path.join("resources", "config.json")
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default if not exists.
        
        Returns:
            Dictionary containing configuration values
        """
        try:
            with open(self.config_file, "r") as f:
                config = json.load(f)
                # Merge with defaults to ensure all required keys exist
                return {**DEFAULT_CONFIG, **config}
        except FileNotFoundError:
            return self._create_default_config()
        except json.JSONDecodeError:
            print(f"Warning: Config file {self.config_file} is corrupted. Using defaults.")
            return self._create_default_config()

    def _create_default_config(self) -> Dict[str, Any]:
        """Create default configuration file.
        
        Returns:
            Dictionary containing default configuration
        """
        # Create resources directory if it doesn't exist
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        
        # Create required directories
        for directory in [
            DEFAULT_CONFIG["output_directory"],
            DEFAULT_CONFIG["backup_directory"]
        ]:
            os.makedirs(directory, exist_ok=True)
            
        # Save default configuration
        self.save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    def save_config(self, config: Dict[str, Any]) -> None:
        """Save configuration to file.
        
        Args:
            config: Configuration dictionary to save
        """
        try:
            with open(self.config_file, "w") as f:
                json.dump(config, f, indent=4)
            self.config = config
        except Exception as e:
            print(f"Error saving configuration: {str(e)}")

    def get(self, key: str) -> Any:
        """Get configuration value.
        
        Args:
            key: Configuration key to retrieve
            
        Returns:
            Configuration value or None if key doesn't exist
        """
        return self.config.get(key)

    def set(self, key: str, value: Any) -> None:
        """Set configuration value and save to file.
        
        Args:
            key: Configuration key to set
            value: Value to set
        """
        self.config[key] = value
        self.save_config(self.config)

    def update(self, updates: Dict[str, Any]) -> None:
        """Update multiple configuration values at once.
        
        Args:
            updates: Dictionary of configuration updates
        """
        self.config.update(updates)
        self.save_config(self.config)

    def reset(self) -> None:
        """Reset configuration to default values."""
        self.config = DEFAULT_CONFIG.copy()
        self.save_config(self.config)

    def verify_paths(self) -> Dict[str, bool]:
        """Verify all configured paths exist.
        
        Returns:
            Dictionary of path keys and their existence status
        """
        path_status = {}
        for key in ['nbt_file', 'progress_file', 'output_directory', 'backup_directory']:
            path = self.config.get(key)
            if path:
                path_status[key] = os.path.exists(path)
        return path_status

    def ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        for directory in [
            self.config['output_directory'],
            self.config['backup_directory']
        ]:
            os.makedirs(directory, exist_ok=True)

    def get_absolute_path(self, key: str) -> Optional[str]:
        """Get absolute path for a configuration path value.
        
        Args:
            key: Configuration key for path
            
        Returns:
            Absolute path or None if key doesn't exist
        """
        path = self.config.get(key)
        if path:
            return str(Path(path).resolve())
        return None

    def validate_nbt_file(self) -> bool:
        """Validate NBT file exists and is accessible.
        
        Returns:
            True if file is valid, False otherwise
        """
        nbt_file = self.get('nbt_file')
        if not nbt_file:
            return False
        
        try:
            return os.path.exists(nbt_file) and os.access(nbt_file, os.R_OK)
        except Exception:
            return False

    @property
    def all_settings(self) -> Dict[str, Any]:
        """Get all current configuration settings.
        
        Returns:
            Dictionary of all configuration values
        """
        return self.config.copy()
