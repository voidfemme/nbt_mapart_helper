"""Network-related utility functions."""

import socket
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_local_ip() -> str:
    """Get the local IP address of the machine.

    This function attempts to determine the machine's local IP address by creating
    a temporary UDP socket connection to a public IP address (8.8.8.8). This causes
    the operating system to select the default network interface that would be used
    for external connections.

    Returns:
        str: The local IP address, or '127.0.0.1' if detection fails

    Note:
        This method doesn't actually send any network traffic - it only creates
        a socket to determine which network interface would be used.
    """
    try:
        # Create a temporary UDP socket
        # Using UDP because we don't actually need to establish a connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        try:
            # 'Connect' to Google's DNS server
            # This won't send any traffic but lets us determine the local IP
            sock.connect(("8.8.8.8", 80))

            # Get the local IP address that was selected for this connection
            local_ip = sock.getsockname()[0]

            return local_ip

        finally:
            # Always close the socket
            sock.close()

    except Exception as e:
        # Log the error but don't crash - return localhost as fallback
        logger.warning(f"Failed to detect local IP address: {str(e)}")
        return "127.0.0.1"


def is_valid_ip(ip_address: str) -> bool:
    """Check if a string is a valid IPv4 address.

    Args:
        ip_address: The string to validate

    Returns:
        bool: True if the string is a valid IPv4 address, False otherwise
    """
    try:
        # Try to pack the IP string as a 4-byte sequence
        socket.inet_pton(socket.AF_INET, ip_address)
        return True
    except (AttributeError, socket.error):
        return False


def is_local_address(ip_address: str) -> bool:
    """Check if an IP address is on the local network.

    Args:
        ip_address: The IP address to check

    Returns:
        bool: True if the address is in local network ranges, False otherwise
    """
    if not is_valid_ip(ip_address):
        return False

    # Check common local network ranges
    return (
        ip_address.startswith("127.")  # Localhost
        or ip_address.startswith("192.168.")  # Common LAN range
        or ip_address.startswith("10.")  # Private network range
        or ip_address.startswith("172.16.")  # Another private range
    )
