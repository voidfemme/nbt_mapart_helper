"""Configuration management for NBT viewer with project isolation."""
import json
import os
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Base configuration values (global settings)
BASE_CONFIG = {
    "auto_save": True,
    "auto_backup": False,
    "backup_interval": 3600,  # seconds
    "lan_enabled": False,
    "lan_port": 8080,
    "lan_discovery_port": 8081,
    "lan_auto_sync": True,
    "lan_sync_interval": 300,  # seconds
    "lan_host_mode": False,
}

# Default project-specific configuration
DEFAULT_PROJECT_CONFIG = {
    "nbt_file": None,  # Will be set during project creation
    "progress_file": None,  # Will be set during project creation
    "output_directory": None,  # Will be set during project creation
    "backup_directory": None,  # Will be set during project creation
    **BASE_CONFIG  # Include all base configuration values
}

class ConfigManager:
    """Manages application configuration settings with project isolation."""

    def __init__(self, base_config_file: Optional[str] = None):
        """Initialize configuration manager.
        
        Args:
            base_config_file: Path to base configuration file. If None, uses default location.
        """
        self.base_dir = Path("resources")
        self.base_config_file = Path(base_config_file) if base_config_file else self.base_dir / "config.json"
        self.current_project = None
        self.config = self._load_base_config()

    def _load_base_config(self) -> Dict[str, Any]:
        """Load base configuration or create default if not exists."""
        try:
            with open(self.base_config_file, "r") as f:
                config = json.load(f)
                return {**BASE_CONFIG, **config}
        except (FileNotFoundError, json.JSONDecodeError):
            return self._create_base_config()

    def _create_base_config(self) -> Dict[str, Any]:
        """Create default base configuration."""
        os.makedirs(self.base_dir, exist_ok=True)
        config = BASE_CONFIG.copy()
        
        with open(self.base_config_file, "w") as f:
            json.dump(config, f, indent=4)
        
        return config

    def _get_project_name(self, nbt_path: str) -> str:
        """Generate project name from NBT file path.
        
        Ensures unique project names by appending a number if necessary.
        """
        base_name = Path(nbt_path).stem
        project_name = base_name
        counter = 1
        
        while (self.base_dir / project_name).exists():
            project_name = f"{base_name}_{counter}"
            counter += 1
            
        return project_name

    def _setup_project_directory(self, project_name: str) -> Path:
        """Set up project directory structure.
        
        Args:
            project_name: Name of the project directory
            
        Returns:
            Path to the project directory
        """
        project_dir = self.base_dir / project_name
        
        # Create project subdirectories
        for subdir in ['output', 'backups']:
            (project_dir / subdir).mkdir(parents=True, exist_ok=True)
            
        return project_dir

    def _validate_project_directory(self, project_dir: Path) -> bool:
        """Validate project directory structure and files.
        
        Args:
            project_dir: Path to project directory
            
        Returns:
            bool: True if valid, False otherwise
        """
        required_files = ['config.json', 'progress.json', 'sessions.json']
        required_dirs = ['output', 'backups']
        
        # Check required files
        for file in required_files:
            if not (project_dir / file).is_file():
                return False
                
        # Check required directories
        for directory in required_dirs:
            if not (project_dir / directory).is_dir():
                return False
                
        # Validate config file contains required fields
        try:
            with open(project_dir / 'config.json', 'r') as f:
                config = json.load(f)
                required_fields = ['nbt_file', 'progress_file', 'output_directory', 'backup_directory']
                return all(field in config for field in required_fields)
        except (json.JSONDecodeError, IOError):
            return False

    def create_project(self, nbt_file: str) -> Dict[str, str]:
        """Create a new project from an NBT file.
        
        Args:
            nbt_file: Path to the NBT file
            
        Returns:
            Dictionary containing project paths
            
        Raises:
            FileNotFoundError: If NBT file doesn't exist
            IOError: If project creation fails
        """
        if not os.path.exists(nbt_file):
            raise FileNotFoundError(f"NBT file not found: {nbt_file}")

        # Generate project name and set up directory
        project_name = self._get_project_name(nbt_file)
        project_dir = self._setup_project_directory(project_name)
        
        try:
            # Copy NBT file to project directory
            nbt_dest = project_dir / Path(nbt_file).name
            shutil.copy2(nbt_file, nbt_dest)
            
            # Create empty progress file
            progress_file = project_dir / "progress.json"
            if not progress_file.exists():
                with open(progress_file, "w") as f:
                    json.dump({
                        "completed_rows": {},
                        "completed_chunks": [],
                        "last_modified": {}
                    }, f, indent=4)

            # Create project config
            project_config = {
                **DEFAULT_PROJECT_CONFIG,
                **self.config,  # Override with any existing base config changes
                "nbt_file": str(nbt_dest),
                "progress_file": str(progress_file),
                "output_directory": str(project_dir / "output"),
                "backup_directory": str(project_dir / "backups")
            }
            
            config_file = project_dir / "config.json"
            with open(config_file, "w") as f:
                json.dump(project_config, f, indent=4)
                
            # Create empty session file
            session_file = project_dir / "sessions.json"
            if not session_file.exists():
                with open(session_file, "w") as f:
                    json.dump({
                        "chunk_locks": {},
                        "active_users": {}
                    }, f, indent=4)

            # Set as current project
            self.current_project = project_name
            self.config = project_config

            return {
                "project_dir": str(project_dir),
                "nbt_file": str(nbt_dest),
                "config_file": str(config_file),
                "progress_file": str(progress_file),
                "session_file": str(session_file)
            }

        except Exception as e:
            # Clean up on failure
            if project_dir.exists():
                shutil.rmtree(project_dir)
            raise IOError(f"Failed to create project: {str(e)}")

    def load_project(self, project_name: str) -> Dict[str, str]:
        """Load an existing project.
        
        Args:
            project_name: Name of the project to load
            
        Returns:
            Dictionary containing project paths
            
        Raises:
            FileNotFoundError: If project or its files don't exist
            ValueError: If project structure is invalid
        """
        project_dir = self.base_dir / project_name
        if not project_dir.exists():
            raise FileNotFoundError(f"Project not found: {project_name}")
            
        if not self._validate_project_directory(project_dir):
            raise ValueError(f"Invalid project structure: {project_name}")
            
        config_file = project_dir / "config.json"
        with open(config_file, "r") as f:
            project_config = json.load(f)
            
        self.current_project = project_name
        self.config = project_config
        
        return {
            "project_dir": str(project_dir),
            "nbt_file": project_config["nbt_file"],
            "config_file": str(config_file),
            "progress_file": project_config["progress_file"],
            "session_file": str(project_dir / "sessions.json")
        }

    def list_projects(self) -> Dict[str, Dict[str, str]]:
        """List all available projects.
        
        Returns:
            Dictionary of project names to their configurations
        """
        projects = {}
        if not self.base_dir.exists():
            return projects
            
        for project_dir in self.base_dir.iterdir():
            if project_dir.is_dir() and self._validate_project_directory(project_dir):
                try:
                    with open(project_dir / "config.json", "r") as f:
                        config = json.load(f)
                    projects[project_dir.name] = config
                except (json.JSONDecodeError, IOError):
                    logger.warning(f"Skipping invalid project: {project_dir.name}")
                    continue
        return projects

    def get(self, key: str) -> Any:
        """Get configuration value."""
        return self.config.get(key)

    def set(self, key: str, value: Any) -> None:
        """Set configuration value and save to current project config.
        
        Args:
            key: Configuration key to set
            value: Value to set
            
        Raises:
            RuntimeError: If no project is currently loaded
        """
        if not self.current_project:
            raise RuntimeError("No project currently loaded")
            
        self.config[key] = value
        config_file = self.base_dir / self.current_project / "config.json"
        
        with open(config_file, "w") as f:
            json.dump(self.config, f, indent=4)

    def is_lan_enabled(self) -> bool:
        """Check if LAN mode is enabled."""
        return self.config.get('lan_enabled', False)

    def toggle_lan_mode(self) -> bool:
        """Toggle LAN mode on/off.
        
        Returns:
            New state of LAN mode (True = enabled, False = disabled)
        """
        new_state = not self.is_lan_enabled()
        self.set('lan_enabled', new_state)
        return new_state

    def get_lan_settings(self) -> Dict[str, Any]:
        """Get all LAN-related settings.
        
        Returns:
            Dictionary containing LAN configuration settings
        """
        return {
            key: self.config.get(key)
            for key in [
                'lan_enabled',
                'lan_port',
                'lan_discovery_port',
                'lan_auto_sync',
                'lan_sync_interval',
                'lan_host_mode'
            ]
        }

    def update(self, updates: Dict[str, Any]) -> None:
        """Update multiple configuration values at once.
        
        Args:
            updates: Dictionary of configuration updates
        """
        if not self.current_project:
            raise RuntimeError("No project currently loaded")
            
        self.config.update(updates)
        config_file = self.base_dir / self.current_project / "config.json"
        
        with open(config_file, "w") as f:
            json.dump(self.config, f, indent=4)

    def reset(self) -> None:
        """Reset configuration to default values."""
        if not self.current_project:
            raise RuntimeError("No project currently loaded")
            
        project_paths = {
            "nbt_file": self.config["nbt_file"],
            "progress_file": self.config["progress_file"],
            "output_directory": self.config["output_directory"],
            "backup_directory": self.config["backup_directory"]
        }
        
        # Reset to defaults while preserving project paths
        self.config = {**DEFAULT_PROJECT_CONFIG, **project_paths}
        config_file = self.base_dir / self.current_project / "config.json"
        
        with open(config_file, "w") as f:
            json.dump(self.config, f, indent=4)

    def verify_paths(self) -> Dict[str, bool]:
        """Verify all configured paths exist.
        
        Returns:
            Dictionary of path keys and their existence status
        """
        if not self.current_project:
            return {}
            
        path_status = {}
        for key in ['nbt_file', 'progress_file', 'output_directory', 'backup_directory']:
            path = self.config.get(key)
            if path:
                path_status[key] = os.path.exists(path)
        return path_status

    def ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        if not self.current_project:
            return
            
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

    def backup_project(self) -> Optional[str]:
        """Create a backup of the current project.
        
        Returns:
            Path to backup directory if successful, None otherwise
        """
        if not self.current_project:
            return None
            
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = Path(self.config['backup_directory']) / f"backup_{timestamp}"
            project_dir = self.base_dir / self.current_project
            
            shutil.copytree(project_dir, backup_dir)
            return str(backup_dir)
            
        except Exception as e:
            logger.error(f"Backup failed: {str(e)}")
            return None

    def delete_project(self, project_name: str) -> bool:
        """Delete a project and all its files.
        
        Args:
            project_name: Name of the project to delete
            
        Returns:
            bool: True if deletion was successful
        """
        project_dir = self.base_dir / project_name
        if not project_dir.exists():
            return False
            
        try:
            shutil.rmtree(project_dir)
            if self.current_project == project_name:
                self.current_project = None
                self.config = self._load_base_config()
            return True
        except Exception as e:
            logger.error(f"Failed to delete project {project_name}: {str(e)}")
            return False
