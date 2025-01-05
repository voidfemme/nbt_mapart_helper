"""Handles file synchronization for NBT Mapart Helper LAN functionality."""

import logging
from typing import Dict, List, Tuple, Any
from datetime import datetime
from dataclasses import dataclass

from src.utils.versioning import VersionTracker

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class FileDiff:
    """Represents differences between file versions."""
    file_id: str
    base_version: int
    changes: Dict[str, Tuple[Any, Any]]  # key -> (old_value, new_value)
    timestamp: str
    author: str


class FileSync:
    """Manages file synchronization between peers."""

    def __init__(self, version_tracker: VersionTracker, username: str):
        """Initialize file synchronization manager.
        
        Args:
            version_tracker: Version tracking instance
            username: Current user's identifier
        """
        self.version_tracker = version_tracker
        self.username = username

    def generate_diff(self, file_id: str, old_content: Dict, new_content: Dict, base_version: int = None) -> FileDiff:
        """Generate diff between two versions of a file.
        
        Args:
            file_id: Identifier for the file
            old_content: Previous version content
            new_content: New version content
            base_version: Version number of the old content (defaults to current version - 1)
            
        Returns:
            FileDiff: Diff object containing changes
        """
        changes = {}
        
        # If no base version provided, use current version - 1 as we're diffing the previous state
        if base_version is None:
            current_version = self.version_tracker.get_current_version(file_id)
            base_version = max(0, current_version - 1)
        
        flat_old = self._flatten_dict(old_content)
        flat_new = self._flatten_dict(new_content)
        
        print(f"\nDEBUG: Generating diff:")
        print(f"Flattened old content: {flat_old}")
        print(f"Flattened new content: {flat_new}")
        
        # Find all changed or new keys
        for key in flat_new:
            if key not in flat_old or flat_old[key] != flat_new[key]:
                changes[key] = (flat_old.get(key), flat_new[key])
                print(f"Recording change for {key}: {flat_old.get(key)} -> {flat_new[key]}")
        
        # Find deleted keys
        for key in flat_old:
            if key not in flat_new:
                changes[key] = (flat_old[key], None)
                print(f"Recording deletion for {key}: {flat_old[key]} -> None")
        
        return FileDiff(
            file_id=file_id,
            base_version=base_version,
            changes=changes,
            timestamp=datetime.now().isoformat(),
            author=self.username
        )

    def apply_diff(self, file_id: str, content: Dict, diff: FileDiff, force: bool = False) -> Tuple[bool, Dict]:
        """Apply diff to file content.
        
        Args:
            file_id: Identifier for the file
            content: Current file content
            diff: Diff to apply
            force: Whether to force apply despite version mismatch
            
        Returns:
            Tuple[bool, Dict]: Success flag and resulting content
        """
        current_version = self.version_tracker.get_current_version(file_id)
        if not force and current_version != diff.base_version:
            logger.warning(
                f"Version mismatch: expected {diff.base_version}, got {current_version}"
            )
            return False, content

        result = content.copy()
        for key, (old_value, new_value) in diff.changes.items():
            if new_value is None:
                # Handle deletion
                self._delete_nested_value(result, key.split('.'))
            else:
                self._set_nested_value(result, key.split('.'), new_value)
                
        return True, result

    def detect_conflicts(self, file_id: str, local_diff: FileDiff, remote_diff: FileDiff) -> List[str]:
        """Detect conflicts between local and remote changes.
        
        Args:
            file_id: Identifier for the file
            local_diff: Local changes
            remote_diff: Remote changes
            
        Returns:
            List[str]: List of conflicting keys
        """
        conflicts = []
        local_keys = set(local_diff.changes.keys())
        remote_keys = set(remote_diff.changes.keys())
        
        print(f"\nDEBUG: Local diff changes: {local_diff.changes}")
        print(f"DEBUG: Remote diff changes: {remote_diff.changes}")
        print(f"DEBUG: Overlapping keys: {local_keys & remote_keys}")
        
        # Check overlapping changes
        for key in local_keys & remote_keys:
            local_old, local_new = local_diff.changes[key]
            remote_old, remote_new = remote_diff.changes[key]
            
            print(f"\nDEBUG: Comparing changes for {key}:")
            print(f"  Local:  {local_old} -> {local_new}")
            print(f"  Remote: {remote_old} -> {remote_new}")
            
            # If both changes have the same new value, it's not a conflict
            if local_new != remote_new:
                print(f"  CONFLICT DETECTED")
                conflicts.append(key)
            else:
                print(f"  No conflict (same new value)")
                
        return conflicts

    def merge_changes(
        self,
        file_id: str,
        content: Dict,
        local_diff: FileDiff,
        remote_diff: FileDiff,
        conflict_resolution: Dict[str, str] | None = None
    ) -> Tuple[bool, Dict]:
        """Merge local and remote changes.
        
        Args:
            file_id: Identifier for the file
            content: Base content to merge into
            local_diff: Local changes
            remote_diff: Remote changes
            conflict_resolution: Dictionary mapping conflicted keys to 'local' or 'remote'
            
        Returns:
            Tuple[bool, Dict]: Success flag and merged content
        """
        conflicts = self.detect_conflicts(file_id, local_diff, remote_diff)
        if conflicts and not conflict_resolution:
            return False, content

        result = content.copy()
        changes_to_apply = {}

        # Apply non-conflicting changes from both diffs
        for key, (_, new_value) in local_diff.changes.items():
            if key not in conflicts:
                changes_to_apply[key] = new_value

        for key, (_, new_value) in remote_diff.changes.items():
            if key not in conflicts:
                changes_to_apply[key] = new_value

        # Handle conflicts according to resolution
        if conflict_resolution:
            for key in conflicts:
                resolution = conflict_resolution.get(key)
                if resolution == 'local':
                    changes_to_apply[key] = local_diff.changes[key][1]  # Use local new value
                elif resolution == 'remote':
                    changes_to_apply[key] = remote_diff.changes[key][1]  # Use remote new value
                else:
                    logger.warning(f"No resolution specified for conflict in key: {key}")
                    return False, content

        # Apply all changes
        for key, value in changes_to_apply.items():
            if value is None:
                self._delete_nested_value(result, key.split('.'))
            else:
                self._set_nested_value(result, key.split('.'), value)

        return True, result

    def _flatten_dict(self, d: Dict, parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
        """Flatten nested dictionary with dot notation."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep).items())
            else:
                items.append((new_key, v))
        return dict(items)

    def _set_nested_value(self, d: Dict, keys: List[str], value: Any) -> None:
        """Set value in nested dictionary using key path."""
        for key in keys[:-1]:
            d = d.setdefault(key, {})
        d[keys[-1]] = value

    def _delete_nested_value(self, d: Dict, keys: List[str]) -> None:
        """Delete value from nested dictionary using key path."""
        current = d
        for key in keys[:-1]:
            if key not in current:
                return
            current = current[key]
            if not isinstance(current, dict):
                return
        if keys[-1] in current:
            del current[keys[-1]]

    def calculate_file_hash(self, content: Dict) -> str:
        """Calculate a hash of file content for integrity checking.
        
        Args:
            content: Dictionary of file content
            
        Returns:
            str: Hash string representing the content
        """
        import hashlib
        import json
        # Sort keys for consistent hashing
        serialized = json.dumps(content, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()
