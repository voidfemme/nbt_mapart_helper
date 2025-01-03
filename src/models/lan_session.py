"""Manages network-aware sessions and collaborative features."""

import os
import json
import fcntl
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
