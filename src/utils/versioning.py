"""Handles version control and change tracking for networked files."""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class ChangeType(Enum):
    """Types of changes that can be tracked."""
    PROGRESS_UPDATE = "progress_update"  # Progress file changes
    SESSION_UPDATE = "session_update"    # Session file changes
    LOCK_ACQUIRE = "lock_acquire"        # Chunk lock acquired
    LOCK_RELEASE = "lock_release"        # Chunk lock released
    SYNC_MARKER = "sync_marker"          # Marks a sync point


@dataclass
class VersionInfo:
    """Information about a specific version."""
    version: int
    timestamp: str
    author: str
    change_type: ChangeType
    chunk_ref: Optional[str] = None
    description: Optional[str] = None


class VersionTracker:
    """Tracks versions and changes for networked files."""

    def __init__(self, version_file: str):
        """Initialize version tracker.
        
        Args:
            version_file: Path to version history file
        """
        self.version_file = version_file
        os.makedirs(os.path.dirname(version_file), exist_ok=True)
        
        self.history: Dict[str, List[VersionInfo]] = {}
        self.current_versions: Dict[str, int] = {}
        self.load_history()

    def load_history(self) -> None:
        """Load version history from file."""
        try:
            with open(self.version_file, "r") as f:
                data = json.load(f)
                self.current_versions = data.get("current_versions", {})
                
                # Convert stored history to VersionInfo objects
                raw_history = data.get("history", {})
                self.history = {
                    file_id: [
                        VersionInfo(
                            version=entry["version"],
                            timestamp=entry["timestamp"],
                            author=entry["author"],
                            change_type=ChangeType(entry["change_type"]),
                            chunk_ref=entry.get("chunk_ref"),
                            description=entry.get("description")
                        )
                        for entry in versions
                    ]
                    for file_id, versions in raw_history.items()
                }
        except FileNotFoundError:
            # Start with empty history if file doesn't exist
            pass
        except json.JSONDecodeError:
            print(f"Warning: Version file {self.version_file} is corrupted. Using empty history.")
            self.history = {}
            self.current_versions = {}

    def save_history(self) -> None:
        """Save version history to file."""
        try:
            # Convert VersionInfo objects to dictionaries
            serializable_history = {
                file_id: [
                    {
                        "version": info.version,
                        "timestamp": info.timestamp,
                        "author": info.author,
                        "change_type": info.change_type.value,
                        "chunk_ref": info.chunk_ref,
                        "description": info.description
                    }
                    for info in versions
                ]
                for file_id, versions in self.history.items()
            }
            
            with open(self.version_file, "w") as f:
                json.dump({
                    "current_versions": self.current_versions,
                    "history": serializable_history
                }, f, indent=4)
        except Exception as e:
            print(f"Error saving version history: {str(e)}")

    def record_change(
        self,
        file_id: str,
        author: str,
        change_type: ChangeType,
        chunk_ref: Optional[str] = None,
        description: Optional[str] = None
    ) -> Tuple[int, str]:
        """Record a change to a file.
        
        Args:
            file_id: Identifier for the file being changed
            author: Username of the person making the change
            change_type: Type of change being made
            chunk_ref: Optional reference to specific chunk being modified
            description: Optional description of the change
            
        Returns:
            Tuple[int, str]: New version number and timestamp
        """
        if file_id not in self.current_versions:
            self.current_versions[file_id] = 0
            self.history[file_id] = []
        
        # Increment version
        new_version = self.current_versions[file_id] + 1
        timestamp = datetime.now().isoformat()
        
        # Create version info
        version_info = VersionInfo(
            version=new_version,
            timestamp=timestamp,
            author=author,
            change_type=change_type,
            chunk_ref=chunk_ref,
            description=description
        )
        
        # Update trackers
        self.current_versions[file_id] = new_version
        self.history[file_id].append(version_info)
        
        # Save changes
        self.save_history()
        
        return new_version, timestamp

    def get_current_version(self, file_id: str) -> int:
        """Get current version number for a file.
        
        Args:
            file_id: Identifier for the file
            
        Returns:
            int: Current version number (0 if file not tracked)
        """
        return self.current_versions.get(file_id, 0)

    def get_changes_since(self, file_id: str, since_version: int) -> List[VersionInfo]:
        """Get list of changes since a specific version.
        
        Args:
            file_id: Identifier for the file
            since_version: Version number to start from
            
        Returns:
            List[VersionInfo]: List of changes since specified version
        """
        if file_id not in self.history:
            return []
        
        return [
            info for info in self.history[file_id]
            if info.version > since_version
        ]

    def check_conflicts(
        self,
        file_id: str,
        local_changes: List[VersionInfo],
        remote_changes: List[VersionInfo]
    ) -> List[Tuple[VersionInfo, VersionInfo]]:
        """Check for potential conflicts between local and remote changes.
        
        Args:
            file_id: Identifier for the file
            local_changes: List of local changes
            remote_changes: List of remote changes
            
        Returns:
            List[Tuple[VersionInfo, VersionInfo]]: List of conflicting change pairs
        """
        conflicts = []
        
        for local in local_changes:
            for remote in remote_changes:
                # Consider changes conflicting if they affect the same chunk
                # within a short time window and are different types
                if (
                    local.chunk_ref == remote.chunk_ref
                    and local.chunk_ref is not None
                    and local.change_type != remote.change_type
                    and abs(datetime.fromisoformat(local.timestamp).timestamp() -
                           datetime.fromisoformat(remote.timestamp).timestamp()) < 300  # 5 min window
                ):
                    conflicts.append((local, remote))
        
        return conflicts

    def mark_sync_point(self, file_id: str, author: str) -> None:
        """Mark a synchronization point in the version history.
        
        Args:
            file_id: Identifier for the file
            author: Username marking the sync point
        """
        self.record_change(
            file_id=file_id,
            author=author,
            change_type=ChangeType.SYNC_MARKER,
            description="Synchronization point"
        )
