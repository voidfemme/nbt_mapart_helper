"""Manages network-aware sessions and collaborative features."""

import os
import json
import fcntl
import requests
import socket
from typing import Dict, List, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

from src.utils.versioning import VersionTracker
from src.models.user_session import UserSession


@dataclass
class NetworkPeer:
    """Information about a network peer."""

    username: str
    ip_address: str
    port: int
    last_seen: str
    is_host: bool = False

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)


class LANSession:
    """Manages network-aware sessions and synchronization."""

    def __init__(
        self,
        username: str,
        session_file: str,
        progress_file: str,
        version_file: str,
        lan_port: int,
    ):
        """Initialize LAN session manager."""
        self.username = username
        self.session_file = session_file
        self.progress_file = progress_file
        self.lan_port = lan_port
        self.peers_file = os.path.join(os.path.dirname(session_file), "peers.json")

        # Initialize version tracking
        self.version_tracker = VersionTracker(version_file)

        # Initialize base session manager
        self.user_session = UserSession(username, session_file)

        # Network-specific state
        self.is_host = False
        self.sync_in_progress = False
        self.last_sync = None

        # Initialize peers file
        self._initialize_peers_file()

        self.host_ip = None
        self.host_port = None
        self.auth_token = None

    def _get_local_ip(self) -> str:
        """Get local IP address."""
        try:
            # Create temporary socket to determine local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"  # Fallback to localhost

    def _handle_sync_conflict(self, file_id: str, response_data: dict) -> None:
        """Handle version conflicts during synchronization.

        Args:
            file_id: Path to the file with conflict
            response_data: Server response containing conflict information
        """
        try:
            print(f"\nVersion conflict detected for {file_id}")
            print("Local changes conflict with remote changes.")
            print("\nOptions:")
            print("1. Keep local version")
            print("2. Use remote version")
            print("3. Skip this file")

            choice = input("\nEnter choice (1-3): ").strip()

            if choice == "1":
                # Force push local version
                with open(file_id, "r") as f:
                    content = json.load(f)
                self._sync_file(
                    file_id, response_data.get("local_version", 0), force=True
                )
                print("Local version kept.")

            elif choice == "2":
                # Get and apply remote version
                response = requests.get(
                    f"http://{self.host_ip}:{self.host_port}/file/{os.path.basename(file_id)}",
                    headers={"Authorization": f"Bearer {self.auth_token}"},
                )
                if response.status_code == 200:
                    with open(file_id, "w") as f:
                        json.dump(response.json(), f, indent=4)
                    print("Remote version applied.")
                else:
                    print("Failed to get remote version.")

            else:
                print("Sync skipped for this file.")

        except Exception as e:
            print(f"Error handling sync conflict: {str(e)}")

    def _sync_file(self, file_id: str, local_version: int, force: bool = False) -> None:
        """Synchronize a specific file with the host.

        Args:
            file_id: Path to the file to sync
            local_version: Current local version of the file
            force: Whether to force push local version
        """
        try:
            with open(file_id, "r") as f:
                content = json.load(f)

            sync_data = {
                "base_version": local_version,
                "content": content,
                "force": force,
            }

            headers = {"Authorization": f"Bearer {self.auth_token}"}

            endpoint = (
                "/sync/progress" if file_id == self.progress_file else "/sync/session"
            )
            response = requests.post(
                f"http://{self.host_ip}:{self.host_port}{endpoint}",
                json=sync_data,
                headers=headers,
            )

            if response.status_code == 409 and not force:
                self._handle_sync_conflict(file_id, response.json())
            elif response.status_code != 200:
                print(f"Sync failed for {file_id}: {response.reason}")

        except Exception as e:
            print(f"Error syncing {file_id}: {str(e)}")

    def _initialize_peers_file(self) -> None:
        """Initialize peers file if it doesn't exist."""
        os.makedirs(os.path.dirname(self.peers_file), exist_ok=True)
        if not os.path.exists(self.peers_file):
            with open(self.peers_file, "w") as f:
                json.dump({"peers": {}}, f, indent=4)

    def _load_peers(self) -> Dict[str, NetworkPeer]:
        """Load peers from file."""
        try:
            with open(self.peers_file, "r") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                data = json.load(f)
                return {
                    username: NetworkPeer(**peer_data)
                    for username, peer_data in data.get("peers", {}).items()
                }
        except Exception as e:
            print(f"Error loading peers: {str(e)}")
            return {}

    def _save_peers(self, peers: Dict[str, NetworkPeer]) -> None:
        """Save peers to file."""
        try:
            with open(self.peers_file, "w") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                data = {
                    "peers": {
                        username: peer.to_dict() for username, peer in peers.items()
                    }
                }
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving peers: {str(e)}")

    def register_peer(
        self, username: str, ip_address: str, port: int, is_host: bool = False
    ) -> bool:
        """Register a new peer on the network."""
        try:
            peers = self._load_peers()

            # Register/update peer
            peers[username] = NetworkPeer(
                username=username,
                ip_address=ip_address,
                port=port,
                last_seen=datetime.now().isoformat(),
                is_host=is_host,
            )

            self._save_peers(peers)
            return True

        except Exception as e:
            print(f"Error registering peer: {str(e)}")
            return False

    def unregister_peer(self, username: str) -> None:
        """Remove a peer from the network."""
        try:
            peers = self._load_peers()
            if username in peers:
                del peers[username]
                self._save_peers(peers)
        except Exception as e:
            print(f"Error unregistering peer: {str(e)}")

    def get_active_peers(self) -> List[NetworkPeer]:
        """Get list of currently active peers."""
        peers = self._load_peers()
        return [
            peer
            for peer in peers.values()
            if self._is_peer_active(peer) and peer.username != self.username
        ]

    def start_host(self) -> bool:
        """Start operating as a host node."""
        try:
            peers = self._load_peers()

            # Check if there's already an active host
            active_hosts = [
                p for p in peers.values() if p.is_host and self._is_peer_active(p)
            ]
            if active_hosts:
                return False

            # Register ourselves as host
            success = self.register_peer(
                username=self.username,
                ip_address="127.0.0.1",
                port=self.lan_port,
                is_host=True,
            )

            if success:
                self.is_host = True
                return True
            return False

        except Exception as e:
            print(f"Error starting host: {str(e)}")
            return False

    def stop_host(self) -> None:
        """Stop operating as a host node."""
        self.is_host = False
        self.unregister_peer(self.username)

    def set_peer_for_testing(self, username: str, peer: NetworkPeer) -> None:
        """Special method for testing - directly set a peer."""
        peers = self._load_peers()
        peers[username] = peer
        self._save_peers(peers)

    def get_sync_status(self) -> Dict[str, Any]:
        """Get current synchronization status."""
        return {
            "sync_in_progress": getattr(self, "sync_in_progress", False),
            "last_sync": getattr(self, "last_sync", None),
            "is_host": getattr(self, "is_host", False),
            "active_peers": len(self.get_active_peers()),
            "progress_version": self.version_tracker.get_current_version(
                self.progress_file
            ),
            "session_version": self.version_tracker.get_current_version(
                self.session_file
            ),
        }

    def _is_peer_active(self, peer: NetworkPeer) -> bool:
        """Check if a peer is considered active."""
        try:
            last_seen = datetime.fromisoformat(peer.last_seen)
            return datetime.now() - last_seen <= timedelta(minutes=5)
        except Exception:
            return False

    def connect_to_host(self, ip_address: str, port: int) -> bool:
        """Connect to a host and initialize synchronization."""
        try:
            # Store host information
            self.host_ip = ip_address
            self.host_port = port

            # Initialize requests session
            response = requests.post(
                f"http://{self.host_ip}:{self.host_port}/auth",
                json={"username": self.username},
                timeout=5,
            )

            if response.status_code != 200:
                print(f"Authentication failed: {response.reason}")
                return False

            self.auth_token = response.json().get("token")

            # Register with the host
            self.register_peer(
                username=self.username,
                ip_address=self._get_local_ip(),
                port=self.lan_port,
                is_host=False,
            )

            # Initial sync
            self._force_sync()
            return True

        except requests.RequestException as e:
            print(f"Connection failed: {str(e)}")
            return False

    def _force_sync(self) -> None:
        """Force immediate synchronization with the host."""
        if not self.auth_token:
            print("Not connected to a host")
            return

        try:
            # Get current versions
            progress_version = self.version_tracker.get_current_version(
                self.progress_file
            )
            session_version = self.version_tracker.get_current_version(
                self.session_file
            )

            # Sync progress file
            self._sync_file(self.progress_file, progress_version)

            # Sync session file
            self._sync_file(self.session_file, session_version)

            self.last_sync = datetime.now().isoformat()

        except Exception as e:
            print(f"Sync failed: {str(e)}")

    def _sync_file(self, file_id: str, local_version: int) -> None:
        """Synchronize a specific file with the host.

        Args:
            file_id: Path to the file to sync
            local_version: Current local version of the file
        """
        try:
            with open(file_id, "r") as f:
                content = json.load(f)

            sync_data = {"base_version": local_version, "content": content}

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.auth_token}",
            }

            endpoint = (
                "/sync/progress" if file_id == self.progress_file else "/sync/session"
            )
            response = requests.post(
                f"http://{self.host_ip}:{self.host_port}{endpoint}",
                json=sync_data,
                headers=headers,
            )

            if response.status_code == 409:
                # Handle version conflict
                print(f"Version conflict detected for {file_id}")
                self._handle_sync_conflict(file_id, response.json())
            elif response.status_code != 200:
                print(f"Sync failed for {file_id}: {response.reason}")

        except Exception as e:
            print(f"Error syncing {file_id}: {str(e)}")

    def cleanup(self) -> None:
        """Clean up network session state."""
        try:
            # First stop being a host if we are one
            if self.is_host:
                self.stop_host()

            # Clean up peer registration
            try:
                self.unregister_peer(self.username)
            except Exception as e:
                print(f"Error unregistering peer: {str(e)}")

            # Clean up the user session
            try:
                self.user_session.cleanup()  # Call parent class cleanup
            except Exception as e:
                print(f"Error in user session cleanup: {str(e)}")

        except Exception as e:
            print(f"Error in LAN session cleanup: {str(e)}")
