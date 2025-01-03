"""Handles user sessions and collaborative features."""

import json
import os
import fcntl
from datetime import datetime
from typing import Dict, List, Optional, Set


class UserSession:
    """Manages user sessions and locks for collaborative editing."""

    def __init__(self, username: str, session_file: str):
        """Initialize user session.

        Args:
            username: Unique identifier for the user
            session_file: Path to session tracking file
        """
        self.username = username
        self.session_file = session_file
        self.active_locks: Set[str] = set()  # Tracks chunks this user has locked

        # Ensure session file exists
        os.makedirs(os.path.dirname(session_file), exist_ok=True)
        if not os.path.exists(session_file):
            with open(session_file, "w") as f:
                json.dump({"chunk_locks": {}, "active_users": {}}, f, indent=4)

    def acquire_chunk_lock(self, chunk_ref: str) -> bool:
        """Attempt to acquire lock for a chunk.

        Args:
            chunk_ref: Reference to the chunk (e.g., 'A1')

        Returns:
            bool: True if lock was acquired, False if chunk is locked by another user
        """
        try:
            with open(self.session_file, "r+") as f:
                # Use file system level locking to handle concurrent access
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)

                try:
                    sessions = json.load(f)
                except json.JSONDecodeError:
                    sessions = {"chunk_locks": {}, "active_users": {}}

                # Check if chunk is already locked
                if chunk_ref in sessions["chunk_locks"]:
                    lock_info = sessions["chunk_locks"][chunk_ref]
                    # Allow re-acquiring our own lock
                    if lock_info["username"] != self.username:
                        return False
                    # If it's our lock, update the timestamp
                    lock_info["timestamp"] = datetime.now().isoformat()
                else:
                    # Acquire new lock
                    sessions["chunk_locks"][chunk_ref] = {
                        "username": self.username,
                        "timestamp": datetime.now().isoformat(),
                    }

                # Update active users
                sessions["active_users"][self.username] = {
                    "last_active": datetime.now().isoformat()
                }

                # Write back to file
                f.seek(0)
                f.truncate()
                json.dump(sessions, f, indent=4)

                self.active_locks.add(chunk_ref)
                return True

        except Exception as e:
            print(f"Error acquiring lock: {str(e)}")
            return False

    def release_chunk_lock(self, chunk_ref: str) -> bool:
        """Release lock on a chunk.

        Args:
            chunk_ref: Reference to the chunk

        Returns:
            bool: True if lock was released successfully
        """
        try:
            with open(self.session_file, "r+") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)

                sessions = json.load(f)

                # Only release if we own the lock
                if chunk_ref in sessions["chunk_locks"]:
                    if sessions["chunk_locks"][chunk_ref]["username"] == self.username:
                        del sessions["chunk_locks"][chunk_ref]
                        self.active_locks.remove(chunk_ref)

                        # Update last active timestamp
                        sessions["active_users"][self.username] = {
                            "last_active": datetime.now().isoformat()
                        }

                        f.seek(0)
                        f.truncate()
                        json.dump(sessions, f, indent=4)
                        return True

            return False

        except Exception as e:
            print(f"Error releasing lock: {str(e)}")
            return False

    def get_lock_info(self, chunk_ref: str) -> Optional[Dict]:
        """Get information about who has locked a chunk.

        Args:
            chunk_ref: Reference to the chunk

        Returns:
            Optional[Dict]: Lock information if chunk is locked, None otherwise
        """
        try:
            with open(self.session_file, "r") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                sessions = json.load(f)
                return sessions["chunk_locks"].get(chunk_ref)
        except Exception:
            return None

    def get_active_users(self) -> List[Dict]:
        """Get list of currently active users.

        Returns:
            List[Dict]: Information about active users
        """
        try:
            with open(self.session_file, "r") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                sessions = json.load(f)
                return [
                    {"username": username, **info}
                    for username, info in sessions["active_users"].items()
                ]
        except Exception:
            return []

    def cleanup(self) -> None:
        """Release all locks held by this user."""
        try:
            with open(self.session_file, "r+") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)

                try:
                    sessions = json.load(f)
                except json.JSONDecodeError:
                    print("Warning: Session file corrupted. Creating new session.")
                    sessions = {"chunk_locks": {}, "active_users": {}}

                # Remove user from active users
                if self.username in sessions["active_users"]:
                    del sessions["active_users"][self.username]

                # Release all locks held by this user
                locks_to_remove = []
                for chunk_ref, lock_info in sessions["chunk_locks"].items():
                    if lock_info["username"] == self.username:
                        locks_to_remove.append(chunk_ref)
                        try:
                            self.active_locks.remove(chunk_ref)
                        except KeyError:
                            pass  # Lock might not be in active_locks set

                # Remove the locks after iterating
                for chunk_ref in locks_to_remove:
                    del sessions["chunk_locks"][chunk_ref]

                # Write back to file
                f.seek(0)
                f.truncate()
                json.dump(sessions, f, indent=4)

        except FileNotFoundError:
            print("Warning: Session file not found during cleanup")
        except Exception as e:
            print(f"Warning: Non-critical error during cleanup: {str(e)}")
