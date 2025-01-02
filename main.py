"""Main entry point for NBT viewer application."""

import sys
import os
from nbtlib import nbt
from typing import Optional

from src.config import ConfigManager
from src.models.chunk import ChunkManager
from src.models.progress import ProgressTracker
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
    format_overall_statistics,
)


class NBTViewer:
    """Main application class for NBT viewer."""

    def __init__(self):
        """Initialize NBT viewer application."""
        self.config = ConfigManager()
        self.load_nbt_file()

    def load_nbt_file(self) -> None:
        """Load NBT file and initialize managers."""
        try:
            self.nbt_file = nbt.load(self.config.get("nbt_file"))
            self.chunk_manager = ChunkManager(self.nbt_file)
            self.progress_tracker = ProgressTracker(self.config.get("progress_file"))
        except FileNotFoundError:
            print(f"Error: NBT file not found at {self.config.get('nbt_file')}")
            self.handle_missing_nbt()
        except Exception as e:
            print(f"Error loading NBT file: {str(e)}")
            sys.exit(1)

    def handle_missing_nbt(self) -> None:
        """Handle missing NBT file scenario."""
        print("\nWould you like to:")
        print("1. Create default config with example file")
        print("2. Specify a new NBT file path")
        choice = input("Enter choice (1/2): ").strip()

        if choice == "1":
            self.config.reset()
            print(f"Created default config at {self.config.config_file}")
            self.load_nbt_file()
        elif choice == "2":
            new_path = input_with_path_completion("Enter the path to your NBT file: ")
            if os.path.exists(new_path):
                self.config.set("nbt_file", new_path)
                print(f"Updated config with new NBT file path: {new_path}")
                self.load_nbt_file()
            else:
                print("Error: Specified file does not exist. Exiting.")
                sys.exit(1)
        else:
            print("Invalid choice. Exiting.")
            sys.exit(1)

    def view_chunk_data(self, chunk_ref: str) -> None:
        """View data for a specific chunk."""
        chunk = self.chunk_manager.get_chunk(chunk_ref)
        if not chunk:
            print(f"Chunk {chunk_ref} not found!")
            return

        chunk_data = chunk.to_dict()
        completed_rows = self.progress_tracker.get_completed_rows(chunk_ref)

        # Print chunk header
        print(f"\nChunk {chunk_ref}:")

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

        # Print separator before statistics
        print("\n" + "-" * 50)

        # Print statistics
        stats = get_chunk_statistics(chunk_data, chunk_ref, self.progress_tracker)
        print(format_chunk_statistics(stats))

        save_option = input("\nWould you like to save this to a file? (y/n): ").lower()
        if save_option == "y":
            filename = f"chunk_{chunk_ref}.txt"
            output_path = os.path.join(self.config.get("output_directory"), filename)

            # Save both row data and statistics
            full_output = []
            full_output.append(f"Chunk {chunk_ref}:")
            for row_num in range(16):
                is_completed = row_num in completed_rows
                if row_num in chunk_data:
                    full_output.append(
                        format_row_data(chunk_data, chunk_ref, row_num, is_completed)
                    )
                else:
                    full_output.append(
                        f"\nChunk {chunk_ref}, Row {row_num}: {'[COMPLETED]' if is_completed else ''}"
                    )
                    full_output.append("No blocks in this row")
            full_output.append("\n" + "-" * 50)
            full_output.append(format_chunk_statistics(stats))

            message = save_chunk_data("\n".join(full_output), output_path)
            print(message)

    def row_by_row_mode(self, chunk_ref: str) -> None:
        """Interactive row-by-row mode for working through a chunk."""
        chunk = self.chunk_manager.get_chunk(chunk_ref)
        if not chunk:
            print(f"Chunk {chunk_ref} not found!")
            return

        current_row = 0
        chunk_data = chunk.to_dict()

        while True:
            # Clear screen (platform independent)
            os.system("cls" if os.name == "nt" else "clear")

            # Show chunk info header
            print(f"\nChunk {chunk_ref} - Row by Row Mode")
            print(f"Current Row: {current_row}/15")
            completed_rows = self.progress_tracker.get_completed_rows(chunk_ref)
            print(f"Completed Rows: {len(completed_rows)}/16")

            # Show current row data
            is_completed = current_row in completed_rows
            print(format_row_data(chunk_data, chunk_ref, current_row, is_completed))

            # Show menu
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
            elif choice == "n":
                if current_row < 15:
                    current_row += 1
            elif choice == "p":
                if current_row > 0:
                    current_row -= 1
            elif choice == "c":
                self.progress_tracker.mark_row_complete(chunk_ref, current_row)
                if self.progress_tracker.is_chunk_complete(chunk_ref):
                    print("\nAll rows completed! Chunk marked as complete.")
                    input("Press Enter to continue...")
            elif choice == "u":
                self.progress_tracker.unmark_row_complete(chunk_ref, current_row)
            else:
                # Try to parse as row number
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

    def change_nbt_file(self) -> None:
        """Change the current NBT file."""
        print("\nUse tab completion to navigate directories")
        new_path = input_with_path_completion("Enter the path to your NBT file: ")
        if os.path.exists(new_path):
            self.config.set("nbt_file", new_path)
            print(f"Updated config with new NBT file path: {new_path}")
            print("Please restart the program to load the new file.")
            sys.exit(0)
        else:
            print("Error: Specified file does not exist.")

    def run(self) -> None:
        """Main application loop."""
        while True:
            print("\nNBT Mapart Helper - Main Menu")
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
            print("Q. Quit")

            choice = input("\nEnter your choice: ").strip().upper()

            if choice == "Q":
                break
            elif choice == "1":
                chunk_ref = input("Enter chunk reference (e.g., A1): ").upper()
                self.view_chunk_data(chunk_ref)
            elif choice == "2":
                chunks = self.chunk_manager.list_chunks()
                print(format_chunk_grid(dict.fromkeys(chunks), self.progress_tracker))

                # Get and display overall statistics
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
                        self.config.get("output_directory"), f"chunk_{chunk_ref}.txt"
                    )

                chunk_data = chunk.to_dict()
                stats = get_chunk_statistics(
                    chunk_data, chunk_ref, self.progress_tracker
                )
                message = save_chunk_data(format_chunk_statistics(stats), filename)
                print(message)
            elif choice == "4":
                chunk_ref = input("Enter chunk reference (e.g., A1): ").upper()
                if not self.chunk_manager.get_chunk(chunk_ref):
                    print(f"Chunk {chunk_ref} not found!")
                    continue
                try:
                    row_num = int(input("Enter row number (0-15): "))
                    if 0 <= row_num <= 15:
                        self.progress_tracker.mark_row_complete(chunk_ref, row_num)
                        print(f"Marked row {row_num} in chunk {chunk_ref} as complete!")
                    else:
                        print("Invalid row number!")
                except ValueError:
                    print("Please enter a valid number.")
            elif choice == "5":
                chunk_ref = input("Enter chunk reference (e.g., A1): ").upper()
                if not self.chunk_manager.get_chunk(chunk_ref):
                    print(f"Chunk {chunk_ref} not found!")
                    continue
                self.progress_tracker.mark_chunk_complete(chunk_ref)
                print(f"Marked chunk {chunk_ref} as complete!")
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
            else:
                print("Invalid choice. Please try again.")

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
        input("\nPress Enter to continue...")


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
