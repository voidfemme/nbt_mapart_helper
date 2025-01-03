"""HTTP server for NBT Mapart Helper LAN synchronization."""

import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional, Tuple
import threading
import logging
from datetime import datetime
from functools import wraps
import secrets

from src.models.lan_session import LANSession
from src.utils.versioning import ChangeType
from src.models.progress import ProgressTracker

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def generate_auth_token() -> str:
    """Generate a secure authentication token."""
    return secrets.token_urlsafe(32)

class SyncServerAuth:
    """Handles authentication for the sync server."""
    
    def __init__(self):
        self.tokens: Dict[str, Dict[str, Any]] = {}
        
    def create_token(self, username: str) -> str:
        """Create new authentication token for a user."""
        token = generate_auth_token()
        self.tokens[token] = {
            "username": username,
            "created": datetime.now().isoformat()
        }
        return token
        
    def validate_token(self, token: str) -> Optional[str]:
        """Validate token and return username if valid."""
        if token in self.tokens:
            return self.tokens[token]["username"]
        return None

    def remove_token(self, token: str) -> None:
        """Remove an authentication token."""
        if token in self.tokens:
            del self.tokens[token]

def require_auth(func):
    """Decorator to require authentication for endpoints."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        auth_header = self.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            self.send_error(401, "Authentication required")
            return None
            
        token = auth_header.split(' ')[1]
        username = self.server.auth.validate_token(token)
        if not username:
            self.send_error(401, "Invalid authentication token")
            return None
            
        return func(self, username, *args, **kwargs)
    return wrapper

class SyncRequestHandler(BaseHTTPRequestHandler):
    """Handler for sync server requests."""
    
    def _send_json_response(self, data: Dict[str, Any], status: int = 200) -> None:
        """Send JSON response with appropriate headers."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _read_json_request(self) -> Optional[Dict[str, Any]]:
        """Read and parse JSON request body."""
        try:
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            return json.loads(body.decode())
        except Exception as e:
            logger.error(f"Error reading request body: {str(e)}")
            return None

    def _is_local_request(self) -> bool:
        """Verify request is from local network."""
        client_ip = self.client_address[0]
        return (
            client_ip.startswith('127.') or
            client_ip.startswith('192.168.') or
            client_ip.startswith('10.') or
            client_ip.startswith('172.16.')
        )

    def do_POST(self) -> None:
        """Handle POST requests."""
        if not self._is_local_request():
            self.send_error(403, "Only local network requests allowed")
            return

        if self.path == '/auth':
            self._handle_auth()
        elif self.path == '/sync/progress':
            self._handle_progress_sync()
        elif self.path == '/sync/session':
            self._handle_session_sync()
        elif self.path == '/lock/acquire':
            self._handle_lock_acquire()
        elif self.path == '/lock/release':
            self._handle_lock_release()
        else:
            self.send_error(404, "Endpoint not found")

    def do_GET(self) -> None:
        """Handle GET requests."""
        if not self._is_local_request():
            self.send_error(403, "Only local network requests allowed")
            return

        if self.path == '/status':
            self._handle_status()
        elif self.path == '/sync/status':
            self._handle_sync_status()
        elif self.path.startswith('/chunks/'):
            self._handle_chunk_data()
        else:
            self.send_error(404, "Endpoint not found")

    def _handle_auth(self) -> None:
        """Handle authentication requests."""
        data = self._read_json_request()
        if not data or 'username' not in data:
            self.send_error(400, "Missing username")
            return
            
        token = self.server.auth.create_token(data['username'])
        self._send_json_response({"token": token})

    @require_auth
    def _handle_status(self, username: str) -> None:
        """Handle status check requests."""
        status = self.server.lan_session.get_sync_status()
        self._send_json_response(status)

    @require_auth
    def _handle_sync_status(self, username: str) -> None:
        """Handle sync status requests."""
        status = {
            "progress_version": self.server.lan_session.version_tracker.get_current_version(
                self.server.lan_session.progress_file
            ),
            "session_version": self.server.lan_session.version_tracker.get_current_version(
                self.server.lan_session.session_file
            ),
            "sync_in_progress": self.server.lan_session.sync_in_progress,
            "last_sync": self.server.lan_session.last_sync
        }
        self._send_json_response(status)

    @require_auth
    def _handle_progress_sync(self, username: str) -> None:
        """Handle progress file synchronization."""
        data = self._read_json_request()
        if not data:
            self.send_error(400, "Invalid request body")
            return
            
        # Check for version conflicts
        local_version = self.server.lan_session.version_tracker.get_current_version(
            self.server.lan_session.progress_file
        )
        if data.get('base_version', 0) != local_version:
            self._send_json_response({
                "status": "conflict",
                "local_version": local_version
            }, status=409)
            return
            
        # Apply changes
        try:
            with open(self.server.lan_session.progress_file, 'w') as f:
                json.dump(data['progress'], f, indent=4)
                
            # Record version change
            self.server.lan_session.version_tracker.record_change(
                file_id=self.server.lan_session.progress_file,
                author=username,
                change_type=ChangeType.PROGRESS_UPDATE,
                description="Progress sync from remote"
            )
            
            self._send_json_response({"status": "success"})
            
        except Exception as e:
            logger.error(f"Error syncing progress: {str(e)}")
            self.send_error(500, "Error syncing progress")

    @require_auth
    def _handle_session_sync(self, username: str) -> None:
        """Handle session file synchronization."""
        data = self._read_json_request()
        if not data:
            self.send_error(400, "Invalid request body")
            return
            
        # Check for version conflicts
        local_version = self.server.lan_session.version_tracker.get_current_version(
            self.server.lan_session.session_file
        )
        if data.get('base_version', 0) != local_version:
            self._send_json_response({
                "status": "conflict",
                "local_version": local_version
            }, status=409)
            return
            
        # Apply changes
        try:
            with open(self.server.lan_session.session_file, 'w') as f:
                json.dump(data['session'], f, indent=4)
                
            # Record version change
            self.server.lan_session.version_tracker.record_change(
                file_id=self.server.lan_session.session_file,
                author=username,
                change_type=ChangeType.SESSION_UPDATE,
                description="Session sync from remote"
            )
            
            self._send_json_response({"status": "success"})
            
        except Exception as e:
            logger.error(f"Error syncing session: {str(e)}")
            self.send_error(500, "Error syncing session")

    @require_auth
    def _handle_lock_acquire(self, username: str) -> None:
        """Handle chunk lock acquisition."""
        data = self._read_json_request()
        if not data or 'chunk_ref' not in data:
            self.send_error(400, "Missing chunk reference")
            return
            
        chunk_ref = data['chunk_ref']
        success = self.server.lan_session.user_session.acquire_chunk_lock(chunk_ref)
        
        if success:
            self.server.lan_session.version_tracker.record_change(
                file_id=self.server.lan_session.session_file,
                author=username,
                change_type=ChangeType.LOCK_ACQUIRE,
                chunk_ref=chunk_ref
            )
            
        self._send_json_response({
            "status": "success" if success else "failed",
            "chunk_ref": chunk_ref,
            "locked": success
        })

    @require_auth
    def _handle_lock_release(self, username: str) -> None:
        """Handle chunk lock release."""
        data = self._read_json_request()
        if not data or 'chunk_ref' not in data:
            self.send_error(400, "Missing chunk reference")
            return
            
        chunk_ref = data['chunk_ref']
        success = self.server.lan_session.user_session.release_chunk_lock(chunk_ref)
        
        if success:
            self.server.lan_session.version_tracker.record_change(
                file_id=self.server.lan_session.session_file,
                author=username,
                change_type=ChangeType.LOCK_RELEASE,
                chunk_ref=chunk_ref
            )
            
        self._send_json_response({
            "status": "success" if success else "failed",
            "chunk_ref": chunk_ref,
            "released": success
        })

    @require_auth
    def _handle_chunk_data(self, username: str) -> None:
        """Handle chunk data requests."""
        chunk_ref = self.path.split('/')[-1]
        if not chunk_ref:
            self.send_error(400, "Missing chunk reference")
            return
            
        # Get chunk data from progress tracker
        progress = ProgressTracker(self.server.lan_session.progress_file)
        completed_rows = progress.get_completed_rows(chunk_ref)
        
        self._send_json_response({
            "chunk_ref": chunk_ref,
            "completed_rows": completed_rows,
            "last_modified": progress.get_last_modified(chunk_ref)
        })

class SyncServer(HTTPServer):
    """HTTP server for NBT Mapart Helper synchronization."""
    
    def __init__(
        self,
        lan_session: LANSession,
        server_address: Tuple[str, int],
        bind_and_activate: bool = True
    ):
        """Initialize sync server.
        
        Args:
            lan_session: LAN session manager instance
            server_address: Tuple of (host, port)
            bind_and_activate: Whether to bind and activate the server
        """
        super().__init__(server_address, SyncRequestHandler, bind_and_activate)
        self.lan_session = lan_session
        self.auth = SyncServerAuth()
        
    def serve_forever_threaded(self) -> threading.Thread:
        """Start server in a separate thread.
        
        Returns:
            threading.Thread: Server thread
        """
        thread = threading.Thread(target=self.serve_forever)
        thread.daemon = True
        thread.start()
        return thread

def create_sync_server(
    lan_session: LANSession,
    port: int = 8080,
    host: str = ''
) -> SyncServer:
    """Create and configure sync server instance.
    
    Args:
        lan_session: LAN session manager
        port: Port to listen on
        host: Host to bind to (empty string for all interfaces)
        
    Returns:
        SyncServer: Configured server instance
    """
    try:
        server = SyncServer(lan_session, (host, port))
        logger.info(f"Created sync server on port {port}")
        return server
    except Exception as e:
        logger.error(f"Error creating sync server: {str(e)}")
        raise
