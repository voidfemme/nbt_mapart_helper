"""HTTP server for NBT Mapart Helper LAN synchronization."""

import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional, Tuple, cast, Type
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
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
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
            "created": datetime.now().isoformat(),
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


class SyncServer(HTTPServer):
    """HTTP server for NBT Mapart Helper synchronization."""

    def __init__(
        self,
        lan_session: LANSession,
        server_address: Tuple[str, int],
        RequestHandlerClass: Type[BaseHTTPRequestHandler],
        bind_and_activate: bool = True,
    ):
        """Initialize sync server.

        Args:
            lan_session: LAN session manager instance
            server_address: Tuple of (host, port)
            bind_and_activate: Whether to bind and activate the server
        """
        super().__init__(server_address, RequestHandlerClass, bind_and_activate)
        self.lan_session: LANSession = lan_session
        self.auth = SyncServerAuth()
        self._stopping: bool = False

    def serve_forever_threaded(self) -> threading.Thread:
        """Start server in a separate thread.

        Returns:
            threading.Thread: Server thread
        """
        thread = threading.Thread(target=self.serve_forever)
        thread.daemon = True
        thread.start()
        return thread


def require_auth(func):
    """Decorator to require authentication for endpoints."""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        auth_header = self.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            self.send_error(401, "Authentication required")
            return None

        token = auth_header.split(" ")[1]
        username = self.server.auth.validate_token(token)
        if not username:
            self.send_error(401, "Invalid authentication token")
            return None

        return func(self, username, *args, **kwargs)

    return wrapper


class SyncRequestHandler(BaseHTTPRequestHandler):
    """Handler for sync server requests."""

    def get_sync_server(self) -> "SyncServer":
        """Get the server instance with proper typing.

        This method safely casts the base server instance to our SyncServer type.
        We use this instead of directly accessing self.server to ensure type safety
        while respecting the original class hierarchy.

        Returns:
            SyncServer: The server instance properly typed"""
        return cast("SyncServer", self.server)

    def _send_json_response(self, data: Dict[str, Any], status: int = 200) -> None:
        """Send JSON response with appropriate headers."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        try:
            response = json.dumps(data)
            self.wfile.write(response.encode())
        except Exception as e:
            logger.error(f"Error sending JSON response: {str(e)}")
            self.send_error(500, "Error generating response")

    def _read_json_request(self) -> Optional[Dict[str, Any]]:
        """Read and parse JSON request body."""
        try:
            content_length = int(self.headers["Content-Length"])
            body = self.rfile.read(content_length)
            return json.loads(body.decode())
        except Exception as e:
            logger.error(f"Error reading request body: {str(e)}")
            return None

    def _is_local_request(self) -> bool:
        """Verify request is from local network."""
        client_ip = self.client_address[0]
        return (
            client_ip.startswith("127.")
            or client_ip.startswith("192.168.")
            or client_ip.startswith("10.")
            or client_ip.startswith("172.16.")
        )

    def _authenticate_request(self, sync_server: "SyncServer") -> Optional[str]:
        """Authenticate an incoming request.

        This helper method extracts and validates the authentication token
        from the request headers. It provides a centralized place for
        authentication logic.

        Args:
            sync_server: The properly typed server instance

        Returns:
            Optional[str]: The authenticated username if valid, None otherwise
        """
        auth_header = self.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        token = auth_header.split(" ")[1]
        return sync_server.auth.validate_token(token)

    def do_POST(self) -> None:
        """Handle POST requests with proper authentication checks.

        This method implements a secure request handling flow:
        1. Verifies the request is from the local network
        2. Gets the server instance with proper typing
        3. Handles authentication (if required)
        4. Routes to the appropriate endpoint handler
        """
        # Get properly typed server instance
        sync_server = self.get_sync_server()

        # Check if request is from local network
        if not self._is_local_request():
            self.send_error(403, "Only local network requests allowed")
            return

        # Special case: /auth endpoint doesn't require authentication
        if self.path == "/auth":
            self._handle_auth()
            return

        # For all other endpoints, authenticate first
        username = self._authenticate_request(sync_server)
        if username is None:
            self.send_error(401, "Authentication required")
            return

        # Now we can safely handle authenticated endpoints
        try:
            if self.path == "/sync/progress":
                self._handle_progress_sync()
            elif self.path == "/sync/session":
                self._handle_session_sync()
            elif self.path == "/lock/acquire":
                self._handle_lock_acquire()
            elif self.path == "/lock/release":
                self._handle_lock_release()
            else:
                self.send_error(404, "Endpoint not found")
        except Exception as e:
            logger.error(f"Error handling request to {self.path}: {str(e)}")
            self.send_error(500, f"Internal server error: {str(e)}")

    def do_GET(self) -> None:
        """Handle GET requests with proper authentication checks.

        This method follows the same secure request handling flow as do_POST:
        1. Verifies the request is from the local network
        2. Gets the server instance with proper typing
        3. Handles authentication
        4. Routes to the appropriate endpoint handler
        """
        # Get properly typed server instance
        sync_server = self.get_sync_server()

        # Check if request is from local network
        if not self._is_local_request():
            self.send_error(403, "Only local network requests allowed")
            return

        # All GET endpoints require authentication
        username = self._authenticate_request(sync_server)
        if username is None:
            self.send_error(401, "Authentication required")
            return

        # Handle authenticated endpoints
        try:
            if self.path == "/status":
                self._handle_status()
            elif self.path == "/sync/status":
                self._handle_sync_status()
            elif self.path.startswith("/chunks/"):
                self._handle_chunk_data()
            else:
                self.send_error(404, "Endpoint not found")
        except Exception as e:
            logger.error(f"Error handling request to {self.path}: {str(e)}")
            self.send_error(500, f"Internal server error: {str(e)}")

    def _handle_auth(self) -> None:
        """Handle authentication requests."""
        sync_server = self.get_sync_server()
        data = self._read_json_request()
        if not data or "username" not in data:
            self.send_error(400, "Missing username")
            return

        token = sync_server.auth.create_token(data["username"])
        self._send_json_response({"token": token})

    @require_auth
    def _handle_status(self, username: str | None) -> None:
        """Handle status check requests."""
        sync_server = self.get_sync_server()
        status = sync_server.lan_session.get_sync_status()
        self._send_json_response(status)

    @require_auth
    def _handle_sync_status(self, username: str | None) -> None:
        """Handle sync status requests."""
        sync_server = self.get_sync_server()

        status = {
            "progress_version": sync_server.lan_session.version_tracker.get_current_version(
                sync_server.lan_session.progress_file
            ),
            "session_version": sync_server.lan_session.version_tracker.get_current_version(
                sync_server.lan_session.session_file
            ),
            "sync_in_progress": sync_server.lan_session.sync_in_progress,
            "last_sync": sync_server.lan_session.last_sync,
        }
        self._send_json_response(status)

    @require_auth
    def _handle_progress_sync(self, username: str) -> None:
        """Handle progress file synchronization.

        This method processes incoming progress sync requests, ensuring proper
        version control and data consistency.

        Args:
            username: The authenticated username making the request
        """
        sync_server = self.get_sync_server()
        try:
            data = self._read_json_request()
            if not data:
                self.send_error(400, "Invalid request body")
                return

            # Validate required fields
            if "content" not in data or "base_version" not in data:
                self.send_error(400, "Missing required fields")
                return

            # Check for version conflicts
            local_version = sync_server.lan_session.version_tracker.get_current_version(
                sync_server.lan_session.progress_file
            )

            if data.get("base_version", 0) != local_version and not data.get(
                "force", False
            ):
                self._send_json_response(
                    {
                        "status": "conflict",
                        "local_version": local_version,
                        "message": "Version mismatch",
                    },
                    status=409,
                )
                return

            # Apply changes
            try:
                with open(sync_server.lan_session.progress_file, "w") as f:
                    json.dump(data["content"], f, indent=4)

                # Record version change
                sync_server.lan_session.version_tracker.record_change(
                    file_id=sync_server.lan_session.progress_file,
                    author=username,
                    change_type=ChangeType.PROGRESS_UPDATE,
                    description="Progress sync from remote",
                )

                self._send_json_response(
                    {"status": "success", "new_version": local_version + 1}
                )

            except Exception as e:
                logger.error(f"Error writing progress file: {str(e)}")
                self.send_error(500, "Error writing progress file")

        except Exception as e:
            logger.error(f"Error in progress sync: {str(e)}")
            self.send_error(500, "Error syncing progress")

    @require_auth
    def _handle_session_sync(self, username: str) -> None:
        """Handle session file synchronization.

        This method processes incoming session sync requests, ensuring proper
        version control and data consistency.

        Args:
            username: The authenticated username making the request
        """
        sync_server = self.get_sync_server()
        try:
            data = self._read_json_request()
            if not data:
                self.send_error(400, "Invalid request body")
                return

            # Validate required fields
            if "content" not in data or "base_version" not in data:
                self.send_error(400, "Missing required fields")
                return

            # Check for version conflicts
            local_version = sync_server.lan_session.version_tracker.get_current_version(
                sync_server.lan_session.session_file
            )

            if data.get("base_version", 0) != local_version and not data.get(
                "force", False
            ):
                self._send_json_response(
                    {
                        "status": "conflict",
                        "local_version": local_version,
                        "message": "Version mismatch",
                    },
                    status=409,
                )
                return

            # Apply changes
            try:
                with open(sync_server.lan_session.session_file, "w") as f:
                    json.dump(data["content"], f, indent=4)

                # Record version change
                sync_server.lan_session.version_tracker.record_change(
                    file_id=sync_server.lan_session.session_file,
                    author=username,
                    change_type=ChangeType.SESSION_UPDATE,
                    description="Session sync from remote",
                )

                self._send_json_response(
                    {"status": "success", "new_version": local_version + 1}
                )

            except Exception as e:
                logger.error(f"Error writing session file: {str(e)}")
                self.send_error(500, "Error writing session file")

        except Exception as e:
            logger.error(f"Error in session sync: {str(e)}")
            self.send_error(500, "Error syncing session")

    @require_auth
    def _handle_lock_acquire(self, username: str) -> None:
        """Handle chunk lock acquisition."""
        sync_server = self.get_sync_server()
        data = self._read_json_request()
        if not data or "chunk_ref" not in data:
            self.send_error(400, "Missing chunk reference")
            return

        chunk_ref = data["chunk_ref"]
        success = sync_server.lan_session.user_session.acquire_chunk_lock(chunk_ref)

        if success:
            sync_server.lan_session.version_tracker.record_change(
                file_id=sync_server.lan_session.session_file,
                author=username,
                change_type=ChangeType.LOCK_ACQUIRE,
                chunk_ref=chunk_ref,
            )

        self._send_json_response(
            {
                "status": "success" if success else "failed",
                "chunk_ref": chunk_ref,
                "locked": success,
            }
        )

    @require_auth
    def _handle_lock_release(self, username: str) -> None:
        """Handle chunk lock release requests.

        This handler ensures that:
        1. The request is properly authenticated
        2. The chunk reference is valid
        3. Only the lock owner can release it
        4. The version tracking is updated appropriately

        Args:
            username: The authenticated username making the request
        """
        sync_server = self.get_sync_server()
        try:
            # First verify we have a valid username
            if not username:
                self.send_error(401, "Authentication required to release lock")
                return

            # Read and validate request data
            data = self._read_json_request()
            if not data or "chunk_ref" not in data:
                self.send_error(400, "Missing chunk reference")
                return

            chunk_ref = data["chunk_ref"]

            # Get current lock information
            current_lock = sync_server.lan_session.user_session.get_lock_info(chunk_ref)

            # Verify lock ownership before releasing
            if current_lock and current_lock["username"] != username:
                self._send_json_response(
                    {
                        "status": "error",
                        "message": f"Lock is owned by {current_lock['username']}, not {username}",
                        "chunk_ref": chunk_ref,
                        "released": False,
                    },
                    status=403,
                )
                return

            # Attempt to release the lock
            success = sync_server.lan_session.user_session.release_chunk_lock(chunk_ref)

            if success:
                # Record the change in version tracking
                sync_server.lan_session.version_tracker.record_change(
                    file_id=sync_server.lan_session.session_file,
                    author=username,
                    change_type=ChangeType.LOCK_RELEASE,
                    chunk_ref=chunk_ref,
                    description=f"Lock released by {username}",
                )

                self._send_json_response(
                    {
                        "status": "success",
                        "message": "Lock released successfully",
                        "chunk_ref": chunk_ref,
                        "released": True,
                    }
                )
            else:
                # Lock release failed for some reason
                self._send_json_response(
                    {
                        "status": "error",
                        "message": "Failed to release lock",
                        "chunk_ref": chunk_ref,
                        "released": False,
                    },
                    status=400,
                )

        except Exception as e:
            logger.error(f"Error in lock release handler: {str(e)}")
            self._send_json_response(
                {
                    "status": "error",
                    "message": f"Server error: {str(e)}",
                    "released": False,
                },
                status=500,
            )

    @require_auth
    def _handle_chunk_data(self, username: str | None) -> None:
        """Handle chunk data requests."""
        sync_server = self.get_sync_server()
        chunk_ref = self.path.split("/")[-1]
        if not chunk_ref:
            self.send_error(400, "Missing chunk reference")
            return

        # Get chunk data from progress tracker
        progress = ProgressTracker(sync_server.lan_session.progress_file)
        completed_rows = progress.get_completed_rows(chunk_ref)

        self._send_json_response(
            {
                "chunk_ref": chunk_ref,
                "completed_rows": completed_rows,
                "last_modified": progress.get_last_modified(chunk_ref),
            }
        )


def create_sync_server(
    lan_session: LANSession, port: int = 8080, host: str = ""
) -> SyncServer:
    """Create and configure sync server instance.

    This function creates a new SyncServer instance with the appropriate request
    handler and network configuration. It sets up error handling and logging
    to help diagnose any issues during server creation.

    Args:
        lan_session: The LANSession instance that manages network state
        port: The network port to listen on (defaults to 8080)
        host: The host address to bind to (empty string means all interfaces)

    Returns:
        SyncServer: A configured server instance ready to handle requests

    Raises:
        OSError: If the server cannot bind to the specified port
        Exception: For other initialization errors
    """
    try:
        # Create server with all required parameters
        server = SyncServer(
            lan_session=lan_session,
            server_address=(host, port),
            RequestHandlerClass=SyncRequestHandler,
        )

        # Log successful creation
        logger.info(f"Created sync server on port {port}")
        return server

    except OSError as e:
        # Specific handling for network-related errors
        logger.error(f"Network error creating sync server: {str(e)}")
        raise

    except Exception as e:
        # Handle any other unexpected errors
        logger.error(f"Unexpected error creating sync server: {str(e)}")
        raise
