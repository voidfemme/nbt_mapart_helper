"""Handles network discovery for LAN functionality."""

import socket
import json
import threading
import time
from typing import Optional, Callable
from dataclasses import dataclass, asdict
from datetime import datetime

@dataclass
class DiscoveryMessage:
    """Message format for network discovery."""
    username: str
    ip_address: str
    port: int
    is_host: bool
    timestamp: str
    message_type: str  # 'announce' or 'response'
    version: int

    def to_json(self) -> str:
        """Convert message to JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> 'DiscoveryMessage':
        """Create message from JSON string."""
        data = json.loads(json_str)
        return cls(**data)


class NetworkDiscovery:
    """Handles peer discovery on the local network."""

    def __init__(
        self,
        username: str,
        port: int,
        on_peer_discovered: Optional[Callable[[DiscoveryMessage], None]] = None
    ):
        """Initialize network discovery.
        
        Args:
            username: User identifier
            port: Port to use for discovery
            on_peer_discovered: Callback for when new peer is found
        """
        self.username = username
        self.port = port
        self.on_peer_discovered = on_peer_discovered
        self.is_host = False
        self.version = 0
        
        # Set up UDP socket for broadcasting
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Bind to all interfaces
        self.sock.bind(('', port))
        
        self._running = False
        self._listen_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start discovery service."""
        if self._running:
            return
            
        self._running = True
        self._listen_thread = threading.Thread(target=self._listen_for_peers)
        self._listen_thread.daemon = True
        self._listen_thread.start()
        
        # Initial announcement
        self.announce()

    def stop(self) -> None:
        """Stop discovery service."""
        self._running = False
        if self._listen_thread:
            self._listen_thread.join()
        self.sock.close()

    def set_host_status(self, is_host: bool) -> None:
        """Update host status."""
        self.is_host = is_host

    def set_version(self, version: int) -> None:
        """Update version number."""
        self.version = version

    def announce(self) -> None:
        """Broadcast presence on network."""
        try:
            message = DiscoveryMessage(
                username=self.username,
                ip_address=self._get_local_ip(),
                port=self.port,
                is_host=self.is_host,
                timestamp=datetime.now().isoformat(),
                message_type='announce',
                version=self.version
            )
            
            # Broadcast to local network
            self.sock.sendto(
                message.to_json().encode(),
                ('<broadcast>', self.port)
            )
        except Exception as e:
            print(f"Error announcing presence: {str(e)}")

    def _listen_for_peers(self) -> None:
        """Listen for peer announcements."""
        try:
            data, addr = self.sock.recvfrom(1024)
            if not data:  # Skip empty messages
                return
                    
            try:
                message = DiscoveryMessage.from_json(data.decode())
            except json.JSONDecodeError:
                return  # Skip invalid JSON messages
                
            # Don't process our own messages
            if message.username == self.username:
                return
                
            # Respond to announcements
            if message.message_type == 'announce':
                response = DiscoveryMessage(
                    username=self.username,
                    ip_address=self._get_local_ip(),
                    port=self.port,
                    is_host=self.is_host,
                    timestamp=datetime.now().isoformat(),
                    message_type='response',
                    version=self.version
                )
                self.sock.sendto(
                    response.to_json().encode(),
                    (message.ip_address, message.port)
                )
                
            # Notify callback
            if self.on_peer_discovered:
                self.on_peer_discovered(message)
                    
        except socket.timeout:
            return  # Just return on timeout
        except Exception as e:
            print(f"Error in peer discovery: {str(e)}")
            return

    def start(self) -> None:
        """Start discovery service."""
        if self._running:
            return
            
        self._running = True
        self._listen_thread = threading.Thread(target=self._listen_loop)
        self._listen_thread.daemon = True
        self._listen_thread.start()
        
        # Initial announcement
        self.announce()

    def _listen_loop(self) -> None:
        """Main listening loop."""
        self.sock.settimeout(1.0)
        while self._running:
            try:
                self._listen_for_peers()
            except Exception as e:
                if self._running:
                    print(f"Critical error in discovery service: {str(e)}")
                time.sleep(1.0)

    def _get_local_ip(self) -> str:
        """Get local IP address."""
        try:
            # Create temporary socket to determine local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return '127.0.0.1'  # Fallback to localhost


def create_discovery_service(
    username: str,
    port: int,
    callback: Optional[Callable[[DiscoveryMessage], None]] = None
) -> NetworkDiscovery:
    """Create and start a discovery service.
    
    Args:
        username: User identifier
        port: Port to use for discovery
        callback: Optional callback for peer discovery
        
    Returns:
        NetworkDiscovery: Configured discovery service instance
    """
    service = NetworkDiscovery(username, port, callback)
    service.start()
    return service
