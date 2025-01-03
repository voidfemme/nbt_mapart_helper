"""Tests for version tracking functionality."""

import os
import shutil
import unittest
from datetime import datetime
from tempfile import mkdtemp

from src.utils.versioning import VersionTracker, ChangeType, VersionInfo


class TestVersionTracker(unittest.TestCase):
    """Test cases for VersionTracker class."""

    def setUp(self):
        """Set up test environment before each test."""
        # Create temporary directory for test files
        self.test_dir = mkdtemp()
        self.version_file = os.path.join(self.test_dir, "versions.json")
        self.tracker = VersionTracker(self.version_file)

    def tearDown(self):
        """Clean up test environment after each test."""
        # Remove temporary directory and all its contents
        shutil.rmtree(self.test_dir)

    def test_record_change(self):
        """Test recording a new change."""
        version, timestamp = self.tracker.record_change(
            file_id="test.json",
            author="test_user",
            change_type=ChangeType.PROGRESS_UPDATE,
            chunk_ref="A1",
            description="Test change"
        )

        # Check version number
        self.assertEqual(version, 1)
        
        # Verify change was recorded
        changes = self.tracker.get_changes_since("test.json", 0)
        self.assertEqual(len(changes), 1)
        
        change = changes[0]
        self.assertEqual(change.version, 1)
        self.assertEqual(change.author, "test_user")
        self.assertEqual(change.change_type, ChangeType.PROGRESS_UPDATE)
        self.assertEqual(change.chunk_ref, "A1")
        self.assertEqual(change.description, "Test change")

    def test_version_persistence(self):
        """Test that versions persist between tracker instances."""
        # Record a change
        self.tracker.record_change(
            file_id="test.json",
            author="test_user",
            change_type=ChangeType.PROGRESS_UPDATE
        )
        
        # Create new tracker instance
        new_tracker = VersionTracker(self.version_file)
        
        # Verify version info was loaded
        self.assertEqual(
            new_tracker.get_current_version("test.json"),
            1
        )

    def test_multiple_files(self):
        """Test tracking versions for multiple files."""
        # Record changes to different files
        self.tracker.record_change(
            file_id="file1.json",
            author="user1",
            change_type=ChangeType.PROGRESS_UPDATE
        )
        self.tracker.record_change(
            file_id="file2.json",
            author="user1",
            change_type=ChangeType.SESSION_UPDATE
        )
        
        # Check versions
        self.assertEqual(self.tracker.get_current_version("file1.json"), 1)
        self.assertEqual(self.tracker.get_current_version("file2.json"), 1)
        self.assertEqual(self.tracker.get_current_version("nonexistent.json"), 0)

    def test_change_history(self):
        """Test retrieving change history."""
        # Record multiple changes
        self.tracker.record_change(
            file_id="test.json",
            author="user1",
            change_type=ChangeType.LOCK_ACQUIRE,
            chunk_ref="A1"
        )
        self.tracker.record_change(
            file_id="test.json",
            author="user1",
            change_type=ChangeType.LOCK_RELEASE,
            chunk_ref="A1"
        )
        
        # Get changes since version 0
        changes = self.tracker.get_changes_since("test.json", 0)
        self.assertEqual(len(changes), 2)
        
        # Get changes since version 1
        changes = self.tracker.get_changes_since("test.json", 1)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].change_type, ChangeType.LOCK_RELEASE)

    def test_conflict_detection(self):
        """Test conflict detection between changes."""
        # Create two changes to the same chunk close in time
        now = datetime.now().isoformat()
        local_change = VersionInfo(
            version=1,
            timestamp=now,
            author="user1",
            change_type=ChangeType.LOCK_ACQUIRE,
            chunk_ref="A1"
        )
        remote_change = VersionInfo(
            version=1,
            timestamp=now,
            author="user2",
            change_type=ChangeType.PROGRESS_UPDATE,
            chunk_ref="A1"
        )
        
        # Check for conflicts
        conflicts = self.tracker.check_conflicts(
            "test.json",
            [local_change],
            [remote_change]
        )
        
        self.assertEqual(len(conflicts), 1)
        local, remote = conflicts[0]
        self.assertEqual(local.author, "user1")
        self.assertEqual(remote.author, "user2")

    def test_sync_marker(self):
        """Test adding sync markers."""
        # Mark sync point
        self.tracker.mark_sync_point("test.json", "user1")
        
        # Verify sync marker was added
        changes = self.tracker.get_changes_since("test.json", 0)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].change_type, ChangeType.SYNC_MARKER)


if __name__ == '__main__':
    unittest.main()
