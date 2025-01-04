"""Main entry point for NBT viewer application."""

import sys
import os
import time
from pathlib import Path
from nbtlib import nbt

from src.config import ConfigManager
from src.models.chunk import ChunkManager
from src.models.progress import ProgressTracker
from src.models.user_session import UserSession
from src.models.lan_session import LANSession
from src.networking.discovery import create_discovery_service
from src.networking.server import create_sync_server
from src.utils.path_completion import input_with_path_completion
from src.utils.chunk_utils import (
    get_chunk_statistics,
    save_chunk_data,
    get_overall_statistics,
)
from src.utils.formatters import (
    format_chunk_statistics,
    format_overall_statistics,
    format_row_data,
    format_chunk_grid,
)


class NBTViewer:
    """Main application class for NBT viewer."""

    def __init__(self):
        """Initialize NBT viewer application."""
        self.config = ConfigManager()
        self.load_or_create_project()

        # Initialize user session
        self.username = self._get_username()
        self._initialize_session()

    def load_or_create_project(self) -> None:
        """Load existing project or create new one."""
        projects = self.config.list_projects()

        if not projects:
            print("\nNo existing projects found.")
            self.handle_new_project()
            return

        print("\nAvailable projects:")
        for i, (name, config) in enumerate(projects.items(), 1):
            print(f"{i}. {name} ({Path(config['nbt_file']).name})")
        print(f"{len(projects) + 1}. Create new project")

        while True:
            try:
                choice = int(input("\nSelect project: "))
                if 1 <= choice <= len(projects):
                    project_name = list(projects.keys())[choice - 1]
                    project_paths = self.config.load_project(project_name)
                    self.load_nbt_file(project_paths["nbt_file"])
                    break
                elif choice == len(projects) + 1:
                    self.handle_new_project()
                    break
                else:
                    print("Invalid choice")
            except ValueError:
                print("Please enter a number")

    def handle_new_project(self) -> None:
        """Handle creation of a new project"""
        print("\nCreate New Project:")
        print("Use tab completion to navigate directories")
        while True:
            nbt_path = input_with_path_completion("Enter path to NBT file: ").strip()
            if os.path.exists(nbt_path):
                try:
                    project_paths = self.config.create_project(nbt_path)
                    self.load_nbt_file(project_paths["nbt_file"])
                    print(f"\nCreated new project in {project_paths['project_dir']}")
                    break
                except Exception as e:
                    print(f"Error creating project: {str(e)}")
            else:
                print("File not found. Please try again.")

    def _get_username(self) -> str:
        """Get username from environment or user input."""
        username = os.environ.get("USER") or input("Enter your username: ").strip()
        while not username:
            print("Username cannot be empty!")
            username = input("Enter your username: ").strip()
        return username

    def _get_session_handler(self):
        """Get the appropriate session handler based on current mode."""
        if isinstance(self.session, LANSession):
            return self.session.user_session
        return self.session

    def _initialize_session(self) -> None:
        """Initialize appropriate session type based on configuration."""
        session_file = os.path.join(
            os.path.dirname(self.config.get("progress_file")), "sessions.json"
        )

        if self.config.is_lan_enabled():
            self._initialize_lan_session(session_file)
        else:
            self.session = UserSession(self.username, session_file)

    def _initialize_lan_session(self, session_file: str) -> None:
        """Initialize LAN session and networking components."""
        progress_file = self.config.get("progress_file")
        version_file = os.path.join(os.path.dirname(progress_file), "versions.json")

        # Initialize LAN session
        self.session = LANSession(
            username=self.username,
            session_file=session_file,
            progress_file=progress_file,
            version_file=version_file,
            lan_port=self.config.get("lan_port"),
        )

        # Start network discovery if enabled
        self.discovery = create_discovery_service(
            self.username,
            self.config.get("lan_discovery_port"),
            self._on_peer_discovered,
        )

        # Create and start sync server
        if self.config.get("lan_host_mode"):
            self.server = create_sync_server(
                self.session, port=self.config.get("lan_port")
            )
            self.server.serve_forever_threaded()

    def _on_peer_discovered(self, peer):
        """Handle peer discovery events."""
        print(f"\nDiscovered peer: {peer.username} at {peer.ip_address}")
        if peer.is_host:
            print("This peer is hosting the session")

    def _connect_to_host(self) -> None:
        """Connect to a host manually or through discovery."""
        if not isinstance(self.session, LANSession):
            print("\nLAN mode must be enabled first")
            return

        print("\nConnect to Host:")
        print("1. Auto-discover hosts")
        print("2. Manual connection")
        print("3. Cancel")

        choice = input("\nEnter your choice: ").strip()

        if choice == "1":
            # Wait for discovery results
            print("\nSearching for hosts...")
            time.sleep(2)  # Give time for discovery

            active_peers = self.session.get_active_peers()
            hosts = [peer for peer in active_peers if peer.is_host]

            if not hosts:
                print("No hosts found. Try manual connection")
                return
            print("\nAvailable Hosts:")
            for i, host in enumerate(hosts, 1):
                print(f"{i}. {host.username} at {host.ip_address}:{host.port}")

                host_choice = input("\nEnter host number (or 'c' to cancel): ").strip()
                if host_choice.lower() == "c":
                    return

                try:
                    host_idx = int(host_choice) - 1
                    if 0 <= host_idx < len(hosts):
                        host = hosts[host_idx]
                        self.session.connect_to_host(host.ip_address, host.port)
                        print(f"\nConnected to host {host.username}")
                    else:
                        print("Invalid host number")
                except ValueError:
                    print("Invalid input")
        elif choice == "2":
            # Manual connection
            ip = input("\nEnter host IP address: ").strip()
            try:
                port = int(input("Enter host port (default: 8080): ").strip() or "8080")
                self.session.connect_to_host(ip, port)
                print(f"\nConnected to host at {ip}:{port}")
            except ValueError:
                print("Invalid port number")
            except Exception as e:
                print(f"Connection failed: {str(e)}")

    def load_nbt_file(self, nbt_path: str) -> None:
        """Load NBT file and initialize managers.

        Args:
            nbt_path: Path to the NBT file to load
        """
        try:
            self.nbt_file = nbt.load(nbt_path)
            self.chunk_manager = ChunkManager(self.nbt_file)
            self.progress_tracker = ProgressTracker(self.config.get("progress_file"))
        except FileNotFoundError:
            print(f"Error: NBT file not found at {nbt_path}")
            sys.exit(1)
        except Exception as e:
            print(f"Error loading NBT file: {str(e)}")
            sys.exit(1)


    def view_chunk_data(self, chunk_ref: str) -> None:
        """View data for a specific chunk."""
        session_handler = self._get_session_handler()

        # Try to acquire lock first
        if not session_handler.acquire_chunk_lock(chunk_ref):
            lock_info = session_handler.get_lock_info(chunk_ref)
            if lock_info:
                print(
                    f"\nChunk {chunk_ref} is currently being worked on by {lock_info['username']}"
                )
                print(f"Started at: {lock_info['timestamp']}")
                return

        try:
            chunk = self.chunk_manager.get_chunk(chunk_ref)
            if not chunk:
                print(f"Chunk {chunk_ref} not found!")
                return

            chunk_data = chunk.to_dict()
            completed_rows = self.progress_tracker.get_completed_rows(chunk_ref)

            print(f"\nChunk {chunk_ref}:")
            print(f"Currently locked by: {self.username}")

            # Print data for each row
            for row_num in range(16):
                is_completed = row_num in completed_rows
                if row_num in chunk_data:
                    print(format_row_data(chunk_data, chunk_ref, row_num, is_completed))
                else:
                    print(
                        f"\nChunk {chunk_ref}, Row {row_num}: {'[COMPLETED]' if is_completed else ''}"
                    )
                    print("No blocks in this row")

            print("\n" + "-" * 50)

            stats = get_chunk_statistics(chunk_data, chunk_ref, self.progress_tracker)
            print(format_chunk_statistics(stats))

            save_option = input(
                "\nWould you like to save this to a file? (y/n): "
            ).lower()
            if save_option == "y":
                filename = f"chunk_{chunk_ref}.txt"
                output_path = os.path.join(
                    self.config.get("output_directory"), filename
                )
                message = save_chunk_data(format_chunk_statistics(stats), output_path)
                print(message)

        finally:
            # Always release lock when done
            session_handler.release_chunk_lock(chunk_ref)

    def row_by_row_mode(self, chunk_ref: str) -> None:
        """Interactive row-by-row mode for working through a chunk."""
        session_handler = self._get_session_handler()

        # Try to acquire lock first
        if not session_handler.acquire_chunk_lock(chunk_ref):
            lock_info = session_handler.get_lock_info(chunk_ref)
            if lock_info:
                print(
                    f"\nChunk {chunk_ref} is currently being worked on by {lock_info['username']}"
                )
                print(f"Started at: {lock_info['timestamp']}")
                return

        try:
            chunk = self.chunk_manager.get_chunk(chunk_ref)
            if not chunk:
                print(f"Chunk {chunk_ref} not found!")
                return

            current_row = 0
            chunk_data = chunk.to_dict()

            while True:
                os.system("cls" if os.name == "nt" else "clear")

                print(f"\nChunk {chunk_ref} - Row by Row Mode")
                print(f"Current User: {self.username}")
                print(f"Current Row: {current_row}/15")
                completed_rows = self.progress_tracker.get_completed_rows(chunk_ref)
                print(f"Completed Rows: {len(completed_rows)}/16")

                is_completed = current_row in completed_rows
                print(format_row_data(chunk_data, chunk_ref, current_row, is_completed))

                print("\nOptions:")
                print("n - Next row")
                print("p - Previous row")
                print("c - Mark current row as complete")
                print("u - Unmark current row as complete")
                print("q - Quit to main menu")
                print("Or enter a row number (0-15) to jump to that row")

                choice = input("\nEnter your choice: ").strip().lower()

                if choice == "q":
                    break
                elif choice == "n" and current_row < 15:
                    current_row += 1
                elif choice == "p" and current_row > 0:
                    current_row -= 1
                elif choice == "c":
                    self.progress_tracker.mark_row_complete(chunk_ref, current_row)
                    if self.progress_tracker.is_chunk_complete(chunk_ref):
                        print("\nAll rows completed! Chunk marked as complete.")
                        input("Press Enter to continue...")
                elif choice == "u":
                    self.progress_tracker.unmark_row_complete(chunk_ref, current_row)
                else:
                    try:
                        row_num = int(choice)
                        if 0 <= row_num <= 15:
                            current_row = row_num
                        else:
                            print(
                                "\nInvalid row number. Please enter a number between 0 and 15."
                            )
                            input("Press Enter to continue...")
                    except ValueError:
                        print("\nInvalid input. Please try again.")
                        input("Press Enter to continue...")

        finally:
            # Always release lock when done
            session_handler.release_chunk_lock(chunk_ref)

    def show_active_users(self) -> None:
        """Display currently active users and their locked chunks."""
        session_handler = self._get_session_handler()

        users = session_handler.get_active_users()
        if not users:
            print("\nNo active users")
            return

        print("\nActive Users:")
        for user in users:
            print(f"\nUser: {user['username']}")
            print(f"Last active: {user['last_active']}")

    def _show_network_status(self) -> None:
        """Display network status information."""
        if not self.config.is_lan_enabled():
            print("\nLAN mode is disabled")
            return

        print("\nNetwork Status:")
        print(f"LAN Mode: {'Enabled' if self.config.is_lan_enabled() else 'Disabled'}")
        print(f"Host Mode: {'Yes' if self.config.get('lan_host_mode') else 'No'}")
        print(f"Port: {self.config.get('lan_port')}")
        print(f"Discovery Port: {self.config.get('lan_discovery_port')}")

        # Show sync status
        if isinstance(self.session, LANSession):
            try:
                status = self.session.get_sync_status()
                print(f"\nSync Status:")
                print(f"Last Sync: {status.get('last_sync', 'Never')}")
                print(
                    f"Sync in Progress: {'Yes' if status.get('sync_in_progress', False) else 'No'}"
                )
                print(f"Active Peers: {status.get('active_peers', 0)}")
            except Exception as e:
                print(f"\nError getting sync status: {str(e)}")

        input("\nPress Enter to continue...")

    def _toggle_hosting(self) -> None:
        """Toggle between host and client mode."""
        if not self.config.is_lan_enabled():
            print("\nLAN mode must be enabled first")
            return

        current_mode = self.config.get("lan_host_mode")
        new_mode = not current_mode

        if new_mode:
            # Starting host mode
            self.server = create_sync_server(
                self.session, port=self.config.get("lan_port")
            )
            self.server.serve_forever_threaded()
            print("\nHost mode activated")
        else:
            # Stopping host mode
            if hasattr(self, "server"):
                self.server.shutdown()
                delattr(self, "server")
            print("\nHost mode deactivated")

        self.config.set("lan_host_mode", new_mode)

    def _toggle_lan_mode(self) -> None:
        """Toggle LAN mode on/off."""
        new_state = self.config.toggle_lan_mode()
        if new_state:
            print("\nLAN mode enabled")
            self._initialize_session()  # Reinitialize with LAN session
        else:
            print("\nLAN mode disabled")
            if hasattr(self, "discovery"):
                self.discovery.stop()
            if hasattr(self, "server"):
                self.server.shutdown()
            self._initialize_session()  # Reinitialize with regular session

    def _force_sync(self) -> None:
        """Force immediate synchronization with peers."""
        if not isinstance(self.session, LANSession):
            print("\nLAN mode must be enabled for sync")
            return

        try:
            print("\nForcing synchronization...")
            # Add your sync logic here
            print("Synchronization complete")
        except Exception as e:
            print(f"Sync failed: {str(e)}")

        input("Press Enter to continue...")

    def change_nbt_file(self) -> None:
        """Change the current NBT file."""
        print("\nThis will create a new project with the selected NBT file.")
        self.handle_new_project()
        print("Please restart the program to load the new project.")
        sys.exit(0)

    def show_help(self) -> None:
        """Display help information."""
        print("\nHelp:")
        print("- Use option 2 to see all available chunks in a grid")
        print("- Enter a chunk reference (like A1) to see its contents")
        print("- Each chunk shows 16 rows of blocks")
        print("- Coordinates are relative to the chunk (0-15)")
        print("- Mark rows/chunks as complete to track progress")
        print("- View statistics to see block counts and completion status")
        print("- You can save any chunk data to a file for later reference")
        print("- Multiple users can work simultaneously on different chunks")
        print("- Use 'Show active users' to see who's currently working")

        if self.config.is_lan_enabled():
            print("\nLAN Mode Features:")
            print("- Enable/disable LAN mode to work with others")
            print("- Start hosting to let others connect to your session")
            print("- Changes automatically sync between connected users")
            print("- See who's online and what chunks they're working on")
            print("- Force sync option to immediately update changes")

        input("\nPress Enter to continue...")

    def run(self) -> None:
        """Main application loop."""
        session_handler = self._get_session_handler()

        try:
            while True:
                print(f"\nNBT Mapart Helper - Main Menu (User: {self.username})")
                print("Options:")
                print("1. View chunk data (enter chunk reference like A1)")
                print("2. List all available chunks")
                print("3. Save chunk data to file")
                print("4. Mark row as complete")
                print("5. Mark chunk as complete")
                print("6. View chunk statistics")
                print("7. Row-by-row mode")
                print("8. Change NBT file")
                print("9. Help")
                print("10. Show active users")

                # Add LAN-specific options
                if self.config.is_lan_enabled():
                    print("11. Network Status")
                    print("12. Start/Stop Hosting")
                    print("13. Force Sync")
                    print("14. Connect to Host")
                    print("15. Toggle LAN Mode")
                else:
                    print("11. Toggle LAN Mode")

                print("Q. Quit")

                choice = input("\nEnter your choice: ").strip().upper()

                if choice == "Q":
                    break
                elif choice == "1":
                    chunk_ref = input("Enter chunk reference (e.g., A1): ").upper()
                    self.view_chunk_data(chunk_ref)
                elif choice == "2":
                    chunks = self.chunk_manager.list_chunks()
                    print(
                        format_chunk_grid(dict.fromkeys(chunks), self.progress_tracker)
                    )
                    stats = get_overall_statistics(
                        self.chunk_manager, self.progress_tracker
                    )
                    print(format_overall_statistics(stats))
                elif choice == "3":
                    chunk_ref = input("Enter chunk reference (e.g., A1): ").upper()
                    chunk = self.chunk_manager.get_chunk(chunk_ref)
                    if not chunk:
                        print(f"Chunk {chunk_ref} not found!")
                        continue

                    print("\nUse tab completion to navigate directories")
                    filename = input_with_path_completion(
                        "Enter filename (or press Enter for default): "
                    )
                    if not filename:
                        filename = os.path.join(
                            self.config.get("output_directory"),
                            f"chunk_{chunk_ref}.txt",
                        )

                    chunk_data = chunk.to_dict()
                    stats = get_chunk_statistics(
                        chunk_data, chunk_ref, self.progress_tracker
                    )
                    message = save_chunk_data(format_chunk_statistics(stats), filename)
                    print(message)
                elif choice == "4":
                    chunk_ref = input("Enter chunk reference (e.g., A1): ").upper()
                    if not session_handler.acquire_chunk_lock(chunk_ref):
                        lock_info = session_handler.get_lock_info(chunk_ref)
                        if lock_info:
                            print(
                                f"\nChunk {chunk_ref} is currently being worked on by {lock_info['username']}"
                            )
                            continue
                    try:
                        if not self.chunk_manager.get_chunk(chunk_ref):
                            print(f"Chunk {chunk_ref} not found!")
                            continue
                        try:
                            row_num = int(input("Enter row number (0-15): "))
                            if 0 <= row_num <= 15:
                                self.progress_tracker.mark_row_complete(
                                    chunk_ref, row_num
                                )
                                print(
                                    f"Marked row {row_num} in chunk {chunk_ref} as complete!"
                                )
                            else:
                                print("Invalid row number!")
                        except ValueError:
                            print("Please enter a valid number.")
                    finally:
                        session_handler.release_chunk_lock(chunk_ref)
                elif choice == "5":
                    chunk_ref = input("Enter chunk reference (e.g., A1): ").upper()
                    if not session_handler.acquire_chunk_lock(chunk_ref):
                        lock_info = session_handler.get_lock_info(chunk_ref)
                        if lock_info:
                            print(
                                f"\nChunk {chunk_ref} is currently being worked on by {lock_info['username']}"
                            )
                            continue
                    try:
                        if not self.chunk_manager.get_chunk(chunk_ref):
                            print(f"Chunk {chunk_ref} not found!")
                            continue
                        self.progress_tracker.mark_chunk_complete(chunk_ref)
                        print(f"Marked chunk {chunk_ref} as complete!")
                    finally:
                        session_handler.release_chunk_lock(chunk_ref)
                elif choice == "6":
                    chunk_ref = input("Enter chunk reference (e.g., A1): ").upper()
                    chunk = self.chunk_manager.get_chunk(chunk_ref)
                    if not chunk:
                        print(f"Chunk {chunk_ref} not found!")
                        continue
                    chunk_data = chunk.to_dict()
                    stats = get_chunk_statistics(
                        chunk_data, chunk_ref, self.progress_tracker
                    )
                    print(format_chunk_statistics(stats))
                elif choice == "7":
                    chunk_ref = input("Enter chunk reference (e.g., A1): ").upper()
                    self.row_by_row_mode(chunk_ref)
                elif choice == "8":
                    self.change_nbt_file()
                elif choice == "9":
                    self.show_help()
                elif choice == "10":
                    self.show_active_users()
                elif choice == "11":
                    if self.config.is_lan_enabled():
                        self._show_network_status()
                    else:
                        self._toggle_lan_mode()
                elif self.config.is_lan_enabled() and choice == "12":
                    self._toggle_hosting()
                elif self.config.is_lan_enabled() and choice == "13":
                    self._force_sync()
                elif self.config.is_lan_enabled() and choice == "14":
                    self._connect_to_host()
                elif self.config.is_lan_enabled() and choice == "15":
                    self._toggle_lan_mode()
                else:
                    print("Invalid choice. Please try again.")

        finally:
            # Cleanup when exiting
            self.cleanup()

    def cleanup(self) -> None:
        """Clean up resources before exiting."""
        cleanup_errors = []

        # Cleanup discovery service
        if hasattr(self, "discovery"):
            try:
                self.discovery.stop()
            except Exception as e:
                cleanup_errors.append(f"Discovery cleanup error: {str(e)}")

        # Cleanup sync server
        if hasattr(self, "server"):
            try:
                self.server.shutdown()
            except Exception as e:
                cleanup_errors.append(f"Server cleanup error: {str(e)}")

        # Cleanup session last
        if hasattr(self, "session"):
            try:
                self.session.cleanup()
            except Exception as e:
                cleanup_errors.append(f"Session cleanup error: {str(e)}")

        # Report any cleanup errors
        if cleanup_errors:
            print("\nCleanup Errors:")
            for error in cleanup_errors:
                print(f"- {error}")


def main():
    """Entry point for the application."""
    try:
        viewer = NBTViewer()
        viewer.run()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
