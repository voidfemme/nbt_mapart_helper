"""Tests for network discovery functionality."""

import unittest
import socket
import time
from unittest.mock import Mock, patch
from datetime import datetime
from typing import Tuple

from src.networking.discovery import (
    NetworkDiscovery,
    DiscoveryMessage,
    create_discovery_service
)


class TestDiscoveryMessage(unittest.TestCase):
    """Test cases for DiscoveryMessage class."""

    def test_message_serialization(self):
        """Test message serialization and deserialization."""
        original = DiscoveryMessage(
            username="test_user",
            ip_address="192.168.1.100",
            port=8080,
            is_host=False,
            timestamp=datetime.now().isoformat(),
            message_type="announce",
            version=1
        )
        
        # Test serialization
        json_str = original.to_json()
        self.assertIsInstance(json_str, str)
        
        # Test deserialization
        recovered = DiscoveryMessage.from_json(json_str)
        self.assertEqual(recovered.username, original.username)
        self.assertEqual(recovered.ip_address, original.ip_address)
        self.assertEqual(recovered.port, original.port)
        self.assertEqual(recovered.is_host, original.is_host)
        self.assertEqual(recovered.timestamp, original.timestamp)
        self.assertEqual(recovered.message_type, original.message_type)
        self.assertEqual(recovered.version, original.version)


class MockSocket:
    """Mock socket for testing network operations."""
    
    def __init__(self):
        self.sent_messages = []
        self.recv_messages = []
        self.closed = False
        self.bound_address = None
        self._local_address = "192.168.1.100"
        self._timeout_count = 0
    
    def setsockopt(self, *args):
        pass
        
    def bind(self, address):
        self.bound_address = address
        
    def sendto(self, data, address):
        self.sent_messages.append((data, address))
        
    def recvfrom(self, buffer_size) -> Tuple[bytes, Tuple[str, int]]:
        if self.recv_messages:
            msg = self.recv_messages.pop(0)
            if isinstance(msg, tuple) and len(msg) == 2:
                return msg
            # If not properly formatted, return with default address
            return msg, (self._local_address, 8080)
            
        # After a few timeouts, raise socket.timeout to help test cleanup
        self._timeout_count += 1
        if self._timeout_count > 3:
            raise socket.timeout()
            
        # Return actual timeout the first few times
        raise socket.timeout()
        
    def settimeout(self, timeout: float) -> None:
        """Mock setting socket timeout."""
        pass
        
    def getsockname(self):
        """Return mock local address."""
        return (self._local_address, 8080)
        
    def close(self):
        self.closed = True


class TestNetworkDiscovery(unittest.TestCase):
    """Test cases for NetworkDiscovery class."""

    def setUp(self):
        """Set up test environment."""
        self.mock_socket = MockSocket()
        self.socket_patcher = patch('socket.socket', return_value=self.mock_socket)
        self.socket_patcher.start()
        
        # Create discovery instance
        self.callback = Mock()
        self.discovery = NetworkDiscovery(
            username="test_user",
            port=8080,
            on_peer_discovered=self.callback
        )

    def tearDown(self):
        """Clean up test environment."""
        self.discovery.stop()
        self.socket_patcher.stop()

    def test_initialization(self):
        """Test proper initialization."""
        self.assertEqual(self.discovery.username, "test_user")
        self.assertEqual(self.discovery.port, 8080)
        self.assertFalse(self.discovery.is_host)
        self.assertEqual(self.discovery.version, 0)
        self.assertIsNotNone(self.discovery.sock)
        self.assertEqual(self.mock_socket.bound_address, ('', 8080))

    def test_announce(self):
        """Test announcement broadcasting."""
        self.discovery.announce()
        
        # Verify message was sent
        self.assertEqual(len(self.mock_socket.sent_messages), 1)
        data, address = self.mock_socket.sent_messages[0]
        
        # Verify message content
        message = DiscoveryMessage.from_json(data.decode())
        self.assertEqual(message.username, "test_user")
        self.assertEqual(message.port, 8080)
        self.assertEqual(message.message_type, "announce")
        
        # Verify broadcast address
        self.assertEqual(address, ('<broadcast>', 8080))

    def test_peer_discovery(self):
        """Test peer discovery and response."""
        # Create mock peer message
        peer_message = DiscoveryMessage(
            username="peer_user",
            ip_address="192.168.1.101",
            port=8080,
            is_host=False,
            timestamp=datetime.now().isoformat(),
            message_type="announce",
            version=1
        )
        
        # Queue the message
        self.mock_socket.recv_messages = [
            (peer_message.to_json().encode(), ("192.168.1.101", 8080))
        ]
        
        # Single call to process the message
        self.discovery._listen_for_peers()
        
        # Verify callback was called with peer message
        self.callback.assert_called_once()
        received_message = self.callback.call_args[0][0]
        self.assertEqual(received_message.username, "peer_user")
        
        # Verify response was sent to peer
        self.assertEqual(len(self.mock_socket.sent_messages), 1)
        response_data = self.mock_socket.sent_messages[0][0]
        response = DiscoveryMessage.from_json(response_data.decode())
        self.assertEqual(response.message_type, "response")
        self.assertEqual(response.username, "test_user")

    def test_host_status_update(self):
        """Test host status updates."""
        self.discovery.set_host_status(True)
        self.discovery.announce()
        
        # Verify host status in announcement
        data = self.mock_socket.sent_messages[-1][0]
        message = DiscoveryMessage.from_json(data.decode())
        self.assertTrue(message.is_host)

    def test_version_update(self):
        """Test version number updates."""
        self.discovery.set_version(42)
        self.discovery.announce()
        
        # Verify version in announcement
        data = self.mock_socket.sent_messages[-1][0]
        message = DiscoveryMessage.from_json(data.decode())
        self.assertEqual(message.version, 42)

    def test_service_cleanup(self):
        """Test proper service cleanup."""
        self.discovery.start()
        self.discovery.stop()
        
        # Verify socket was closed
        self.assertTrue(self.mock_socket.closed)
        self.assertFalse(self.discovery._running)

    def test_ignore_self_messages(self):
        """Test that own messages are ignored."""
        # Create message from self
        self_message = DiscoveryMessage(
            username="test_user",  # Same as discovery service
            ip_address="192.168.1.100",
            port=8080,
            is_host=False,
            timestamp=datetime.now().isoformat(),
            message_type="announce",
            version=0
        )
        
        # Add message to mock socket's receive queue
        self.mock_socket.recv_messages.append(
            (self_message.to_json().encode(), ("192.168.1.100", 8080))
        )
        
        # Start discovery service
        self.discovery.start()
        time.sleep(0.1)  # Allow time for message processing
        
        # Verify callback was not called
        self.callback.assert_not_called()


class TestDiscoveryServiceCreation(unittest.TestCase):
    """Test cases for discovery service creation."""

    def setUp(self):
        """Set up test environment."""
        self.mock_socket = MockSocket()
        self.socket_patcher = patch('socket.socket', return_value=self.mock_socket)
        self.socket_patcher.start()

    def tearDown(self):
        """Clean up test environment."""
        self.socket_patcher.stop()

    def test_create_discovery_service(self):
        """Test service creation helper function."""
        callback = Mock()
        service = create_discovery_service("test_user", 8080, callback)
        
        self.assertIsInstance(service, NetworkDiscovery)
        self.assertEqual(service.username, "test_user")
        self.assertEqual(service.port, 8080)
        self.assertEqual(service.on_peer_discovered, callback)
        self.assertTrue(service._running)
        
        # Cleanup
        service.stop()


if __name__ == '__main__':
    unittest.main()
