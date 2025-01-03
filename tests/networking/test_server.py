"""Tests for NBT Mapart Helper HTTP synchronization server."""

import unittest
import json
import http.client
import tempfile
import os
import time
from unittest.mock import Mock

from src.networking.server import (
    SyncServer,
    SyncServerAuth,
    create_sync_server,
)
from src.utils.versioning import VersionTracker, ChangeType

class MockLANSession:
    """Mock LAN session for testing."""
    
    def __init__(self):
        # Create temporary files for testing
        self.temp_dir = tempfile.mkdtemp()
        self.progress_file = os.path.join(self.temp_dir, "progress.json")
        self.session_file = os.path.join(self.temp_dir, "sessions.json")
        self.version_file = os.path.join(self.temp_dir, "versions.json")
        
        # Initialize with empty files
        for file in [self.progress_file, self.session_file]:
            with open(file, 'w') as f:
                json.dump({}, f)
        
        # Create real version tracker
        self.version_tracker = VersionTracker(self.version_file)
        
        # Mock user session
        self.user_session = Mock()
        self.user_session.acquire_chunk_lock = Mock(return_value=True)
        self.user_session.release_chunk_lock = Mock(return_value=True)
        
        # Mock state
        self.sync_in_progress = False
        self.last_sync = None
        self.is_host = False
    
    def get_sync_status(self):
        """Mock implementation of get_sync_status."""
        return {
            "in_progress": self.sync_in_progress,
            "last_sync": self.last_sync,
            "is_host": self.is_host,
            "active_peers": 0,
            "progress_version": self.version_tracker.get_current_version(self.progress_file),
            "session_version": self.version_tracker.get_current_version(self.session_file)
        }
        
    def cleanup(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir)

class TestSyncServerAuth(unittest.TestCase):
    """Test authentication functionality."""
    
    def setUp(self):
        self.auth = SyncServerAuth()
        
    def test_token_generation(self):
        """Test token generation and validation."""
        token = self.auth.create_token("test_user")
        self.assertIsNotNone(token)
        self.assertTrue(len(token) > 32)  # Ensure sufficient length for security
        
        # Verify token
        username = self.auth.validate_token(token)
        self.assertEqual(username, "test_user")
        
    def test_invalid_token(self):
        """Test invalid token handling."""
        username = self.auth.validate_token("invalid_token")
        self.assertIsNone(username)
        
    def test_token_removal(self):
        """Test token removal."""
        token = self.auth.create_token("test_user")
        self.auth.remove_token(token)
        username = self.auth.validate_token(token)
        self.assertIsNone(username)

class TestSyncServer(unittest.TestCase):
    """Test server functionality."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment."""
        cls.test_port = 8081
        cls.lan_session = MockLANSession()
        cls.server = create_sync_server(cls.lan_session, cls.test_port)
        cls.server_thread = cls.server.serve_forever_threaded()
        
        # Wait for server to start
        time.sleep(0.1)
        
    @classmethod
    def tearDownClass(cls):
        """Clean up test environment."""
        cls.server.shutdown()
        cls.server.server_close()  # Close the server socket
        cls.server_thread.join()
        cls.lan_session.cleanup()
    
    def setUp(self):
        """Set up for each test."""
        self.conn = http.client.HTTPConnection(f"localhost:{self.test_port}")
        
        # Get auth token
        self.conn.request(
            "POST",
            "/auth",
            body=json.dumps({"username": "test_user"}),
            headers={"Content-Type": "application/json"}
        )
        response = self.conn.getresponse()
        self.token = json.loads(response.read())["token"]
        self.auth_headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
    def tearDown(self):
        """Clean up after each test."""
        self.conn.close()
        
    def test_auth_required(self):
        """Test authentication requirement."""
        self.conn.request("GET", "/status")
        response = self.conn.getresponse()
        self.assertEqual(response.status, 401)
        
    def test_invalid_auth(self):
        """Test invalid authentication handling."""
        headers = {
            "Authorization": "Bearer invalid_token",
            "Content-Type": "application/json"
        }
        self.conn.request("GET", "/status", headers=headers)
        response = self.conn.getresponse()
        self.assertEqual(response.status, 401)
        
    def test_status_endpoint(self):
        """Test status endpoint."""
        self.conn.request("GET", "/status", headers=self.auth_headers)
        response = self.conn.getresponse()
        self.assertEqual(response.status, 200)
        data = json.loads(response.read())
        self.assertIn("progress_version", data)
        self.assertIn("session_version", data)
        
    def test_progress_sync(self):
        """Test progress synchronization."""
        test_progress = {
            "completed_rows": {"A1": [0, 1, 2]},
            "completed_chunks": ["A1"],
            "last_modified": {}
        }
        
        body = {
            "progress": test_progress,
            "base_version": 0
        }
        
        self.conn.request(
            "POST",
            "/sync/progress",
            body=json.dumps(body),
            headers=self.auth_headers
        )
        response = self.conn.getresponse()
        self.assertEqual(response.status, 200)
        
        # Verify file was updated
        with open(self.lan_session.progress_file, 'r') as f:
            saved_progress = json.load(f)
            self.assertEqual(saved_progress, test_progress)
            
    def test_version_conflict(self):
        """Test version conflict handling."""
        # Create initial version
        self.lan_session.version_tracker.record_change(
            self.lan_session.progress_file,
            "other_user",
            ChangeType.PROGRESS_UPDATE
        )
        
        # Try to sync with old version
        body = {
            "progress": {},
            "base_version": 0  # Old version
        }
        
        self.conn.request(
            "POST",
            "/sync/progress",
            body=json.dumps(body),
            headers=self.auth_headers
        )
        response = self.conn.getresponse()
        self.assertEqual(response.status, 409)  # Conflict
        
    def test_lock_management(self):
        """Test chunk lock management."""
        # Test lock acquisition
        body = {"chunk_ref": "A1"}
        self.conn.request(
            "POST",
            "/lock/acquire",
            body=json.dumps(body),
            headers=self.auth_headers
        )
        response = self.conn.getresponse()
        self.assertEqual(response.status, 200)
        data = json.loads(response.read())
        self.assertTrue(data["locked"])
        
        # Test lock release
        self.conn.request(
            "POST",
            "/lock/release",
            body=json.dumps(body),
            headers=self.auth_headers
        )
        response = self.conn.getresponse()
        self.assertEqual(response.status, 200)
        data = json.loads(response.read())
        self.assertTrue(data["released"])
        
    def test_chunk_data(self):
        """Test chunk data retrieval."""
        # Set up some test data
        with open(self.lan_session.progress_file, 'w') as f:
            json.dump({
                "completed_rows": {"A1": [0, 1, 2]},
                "last_modified": {"A1": "2024-01-01T00:00:00"}
            }, f)
            
        self.conn.request("GET", "/chunks/A1", headers=self.auth_headers)
        response = self.conn.getresponse()
        self.assertEqual(response.status, 200)
        data = json.loads(response.read())
        self.assertEqual(data["chunk_ref"], "A1")
        self.assertEqual(data["completed_rows"], [0, 1, 2])

class TestServerCreation(unittest.TestCase):
    """Test server creation and configuration."""
    
    def test_create_server(self):
        """Test server creation."""
        lan_session = MockLANSession()
        try:
            server = create_sync_server(lan_session, port=8082)
            self.assertIsInstance(server, SyncServer)
            self.assertEqual(server.server_address[1], 8082)
        finally:
            lan_session.cleanup()
            
    def test_invalid_port(self):
        """Test handling of invalid port."""
        lan_session = MockLANSession()
        try:
            with self.assertRaises(Exception):
                create_sync_server(lan_session, port=-1)
        finally:
            lan_session.cleanup()

if __name__ == '__main__':
    unittest.main()
