"""Model for tracking progress through chunks."""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any


class ProgressTracker:
    """Tracks completion progress of chunks and rows."""

    def __init__(self, save_file: str):
        """Initialize progress tracker.
        
        Args:
            save_file: Path to the progress save file
        """
        self.save_file = save_file
        os.makedirs(os.path.dirname(self.save_file), exist_ok=True)
        self.progress: Dict[str, Any] = {
            "completed_rows": {},  # Format: {'A1': [0,1,2]} for completed rows
            "completed_chunks": [],  # List of completed chunks
            "last_modified": {},  # Timestamp of last modification
        }
        self.load_progress()

    def load_progress(self) -> None:
        """Load progress from save file."""
        try:
            with open(self.save_file, "r") as f:
                loaded_progress = json.load(f)
                # Update progress while preserving structure
                self.progress["completed_rows"].update(loaded_progress.get("completed_rows", {}))
                self.progress["completed_chunks"].extend(loaded_progress.get("completed_chunks", []))
                self.progress["last_modified"].update(loaded_progress.get("last_modified", {}))
        except FileNotFoundError:
            # File doesn't exist yet, use default empty progress
            pass
        except json.JSONDecodeError:
            print(f"Warning: Progress file {self.save_file} is corrupted. Using empty progress.")

    def save_progress(self) -> None:
        """Save progress to file."""
        try:
            with open(self.save_file, "w") as f:
                json.dump(self.progress, f, indent=4)
        except Exception as e:
            print(f"Error saving progress: {str(e)}")

    def mark_row_complete(self, chunk_ref: str, row_num: int) -> None:
        """Mark a row as complete.
        
        Args:
            chunk_ref: Chunk reference (e.g., 'A1')
            row_num: Row number to mark complete
        """
        if not 0 <= row_num <= 15:
            raise ValueError("Row number must be between 0 and 15")

        if chunk_ref not in self.progress["completed_rows"]:
            self.progress["completed_rows"][chunk_ref] = []

        if row_num not in self.progress["completed_rows"][chunk_ref]:
            self.progress["completed_rows"][chunk_ref].append(row_num)
            self.progress["last_modified"][chunk_ref] = datetime.now().isoformat()

            # Check if all rows are complete
            if len(self.progress["completed_rows"][chunk_ref]) == 16:
                self.mark_chunk_complete(chunk_ref)

            self.save_progress()

    def unmark_row_complete(self, chunk_ref: str, row_num: int) -> None:
        """Remove completed status from a row.
        
        Args:
            chunk_ref: Chunk reference (e.g., 'A1')
            row_num: Row number to unmark
        """
        if (
            chunk_ref in self.progress["completed_rows"]
            and row_num in self.progress["completed_rows"][chunk_ref]
        ):
            self.progress["completed_rows"][chunk_ref].remove(row_num)
            
            # If chunk was marked complete, unmark it
            if chunk_ref in self.progress["completed_chunks"]:
                self.progress["completed_chunks"].remove(chunk_ref)
            
            self.progress["last_modified"][chunk_ref] = datetime.now().isoformat()
            self.save_progress()

    def mark_chunk_complete(self, chunk_ref: str) -> None:
        """Mark an entire chunk as complete.
        
        Args:
            chunk_ref: Chunk reference to mark complete
        """
        if chunk_ref not in self.progress["completed_chunks"]:
            self.progress["completed_chunks"].append(chunk_ref)
            # Mark all rows in the chunk as complete
            self.progress["completed_rows"][chunk_ref] = list(range(16))
            self.progress["last_modified"][chunk_ref] = datetime.now().isoformat()
            self.save_progress()

    def unmark_chunk_complete(self, chunk_ref: str) -> None:
        """Remove completed status from a chunk.
        
        Args:
            chunk_ref: Chunk reference to unmark
        """
        if chunk_ref in self.progress["completed_chunks"]:
            self.progress["completed_chunks"].remove(chunk_ref)
            if chunk_ref in self.progress["completed_rows"]:
                del self.progress["completed_rows"][chunk_ref]
            self.progress["last_modified"][chunk_ref] = datetime.now().isoformat()
            self.save_progress()

    def get_completed_rows(self, chunk_ref: str) -> List[int]:
        """Get list of completed rows for a chunk.
        
        Args:
            chunk_ref: Chunk reference to check
            
        Returns:
            List of completed row numbers
        """
        return sorted(self.progress["completed_rows"].get(chunk_ref, []))

    def is_row_complete(self, chunk_ref: str, row_num: int) -> bool:
        """Check if a specific row is marked complete.
        
        Args:
            chunk_ref: Chunk reference to check
            row_num: Row number to check
            
        Returns:
            True if row is marked complete, False otherwise
        """
        return row_num in self.get_completed_rows(chunk_ref)

    def is_chunk_complete(self, chunk_ref: str) -> bool:
        """Check if a chunk is marked complete.
        
        Args:
            chunk_ref: Chunk reference to check
            
        Returns:
            True if chunk is marked complete, False otherwise
        """
        return chunk_ref in self.progress["completed_chunks"]

    def get_completion_stats(self) -> Dict[str, Any]:
        """Get overall completion statistics.
        
        Returns:
            Dictionary containing completion statistics
        """
        total_chunks = len(self.progress["completed_rows"])
        completed_chunks = len(self.progress["completed_chunks"])
        
        total_rows = 0
        completed_rows = 0
        for chunk_rows in self.progress["completed_rows"].values():
            total_rows += 16  # Each chunk has 16 rows
            completed_rows += len(chunk_rows)

        return {
            "total_chunks": total_chunks,
            "completed_chunks": completed_chunks,
            "chunk_completion_percentage": (completed_chunks / total_chunks * 100) if total_chunks else 0,
            "total_rows": total_rows,
            "completed_rows": completed_rows,
            "row_completion_percentage": (completed_rows / total_rows * 100) if total_rows else 0,
        }

    def get_last_modified(self, chunk_ref: str) -> Optional[str]:
        """Get the last modification timestamp for a chunk.
        
        Args:
            chunk_ref: Chunk reference to check
            
        Returns:
            ISO format timestamp string or None if no modifications recorded
        """
        return self.progress["last_modified"].get(chunk_ref)
