"""Tests for file synchronization functionality."""

import unittest
import os
import tempfile
from copy import deepcopy

from src.utils.versioning import VersionTracker, ChangeType
from src.networking.sync import FileSync


class TestFileSync(unittest.TestCase):
    """Test cases for FileSync class."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.version_file = os.path.join(self.test_dir, "versions.json")
        
        # Initialize version tracker
        self.version_tracker = VersionTracker(self.version_file)
        
        # Initialize file sync
        self.sync = FileSync(self.version_tracker, "test_user")
        
        print("\nDEBUG: Setting up test data...")
        # Sample file contents
        self.old_content = {
            "completed_rows": {
                "A1": [0, 1, 2],  # Should be original state
                "B1": [0, 1]
            },
            "completed_chunks": ["A1"],
            "last_modified": {
                "A1": "2024-01-01T00:00:00",
                "B1": "2024-01-01T00:00:00"
            }
        }
        print(f"DEBUG: old_content A1 = {self.old_content['completed_rows']['A1']}")
        
        self.new_content = {
            "completed_rows": {
                "A1": [0, 1, 2, 3],  # Example change
                "B1": [0, 1],
                "C1": [0]
            },
            "completed_chunks": ["A1"],
            "last_modified": {
                "A1": "2024-01-02T00:00:00",
                "B1": "2024-01-01T00:00:00",
                "C1": "2024-01-02T00:00:00"
            }
        }

    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.test_dir)

    def test_generate_diff(self):
        """Test diff generation between file versions."""
        diff = self.sync.generate_diff("test.json", self.old_content, self.new_content, base_version=0)
        
        self.assertIsNotNone(diff)
        self.assertEqual(diff.file_id, "test.json")
        self.assertEqual(diff.base_version, 0)
        self.assertEqual(diff.author, "test_user")
        
        # Verify changes were detected
        self.assertIn("completed_rows.A1", diff.changes)
        self.assertIn("completed_rows.C1", diff.changes)

    def test_apply_diff(self):
        """Test applying diffs to file content."""
        # Generate diff with explicit base version
        diff = self.sync.generate_diff("test.json", self.old_content, self.new_content, base_version=0)
        
        # Apply diff to old content
        success, result = self.sync.apply_diff("test.json", self.old_content, diff)
        
        self.assertTrue(success)
        self.assertEqual(result["completed_rows"]["A1"], [0, 1, 2, 3])
        self.assertIn("C1", result["completed_rows"])
        self.assertEqual(result["last_modified"]["A1"], "2024-01-02T00:00:00")

    def test_version_mismatch(self):
        """Test handling of version mismatches."""
        print("\n=== Debug: Version Mismatch Test ===")
        initial_version = self.version_tracker.get_current_version("test.json")
        print("Initial version:", initial_version)
        
        # Record a change to increment version
        self.version_tracker.record_change(
            "test.json",
            "other_user",
            ChangeType.PROGRESS_UPDATE
        )
        
        new_version = self.version_tracker.get_current_version("test.json")
        print("After change version:", new_version)
        
        # Generate diff with old version explicitly
        diff = self.sync.generate_diff("test.json", self.old_content, self.new_content, base_version=initial_version)
        
        # Verify diff uses the old version as base
        self.assertEqual(diff.base_version, initial_version)
        print("Generated diff base version:", diff.base_version)
        
        # Try to apply diff
        success, result = self.sync.apply_diff("test.json", self.old_content, diff)
        print("Apply result:", "success" if success else "failed")
        
        self.assertFalse(success)
        self.assertEqual(result, self.old_content)

    def test_conflict_detection(self):
        """Test detection of conflicting changes."""
        # Create conflicting changes
        local_content = deepcopy(self.old_content)
        local_content["completed_rows"]["A1"] = [0, 1, 2, 3]
        
        remote_content = deepcopy(self.old_content)
        remote_content["completed_rows"]["A1"] = [0, 1, 2, 4]
        
        print("\n=== Debug: Conflict Detection Test ===")
        print("Original A1:", self.old_content["completed_rows"]["A1"])
        print("Local A1:", local_content["completed_rows"]["A1"])
        print("Remote A1:", remote_content["completed_rows"]["A1"])
        
        local_diff = self.sync.generate_diff("test.json", self.old_content, local_content, base_version=0)
        remote_diff = self.sync.generate_diff("test.json", self.old_content, remote_content, base_version=0)
        
        print("\nLocal diff changes:", local_diff.changes)
        print("Remote diff changes:", remote_diff.changes)
        
        conflicts = self.sync.detect_conflicts("test.json", local_diff, remote_diff)
        print("\nDetected conflicts:", conflicts)
        
        self.assertEqual(len(conflicts), 1)
        self.assertIn("completed_rows.A1", conflicts)

    def test_merge_changes(self):
        """Test merging non-conflicting changes."""
        # Create non-conflicting changes
        local_content = deepcopy(self.old_content)
        local_content["completed_rows"]["B1"] = [0, 1, 2]
        
        remote_content = deepcopy(self.old_content)
        remote_content["completed_rows"]["C1"] = [0, 1]
        
        local_diff = self.sync.generate_diff("test.json", self.old_content, local_content, base_version=0)
        remote_diff = self.sync.generate_diff("test.json", self.old_content, remote_content, base_version=0)
        
        success, result = self.sync.merge_changes(
            "test.json",
            self.old_content,
            local_diff,
            remote_diff
        )
        
        self.assertTrue(success)
        self.assertEqual(result["completed_rows"]["B1"], [0, 1, 2])
        self.assertEqual(result["completed_rows"]["C1"], [0, 1])

    def test_conflict_resolution(self):
        """Test resolving conflicts with explicit resolution."""
        print("\n=== Debug: Conflict Resolution Test ===")
        
        # Create conflicting changes
        local_content = deepcopy(self.old_content)
        local_content["completed_rows"]["A1"] = [0, 1, 2, 3]
        
        remote_content = deepcopy(self.old_content)
        remote_content["completed_rows"]["A1"] = [0, 1, 2, 4]
        
        print("Original A1:", self.old_content["completed_rows"]["A1"])
        print("Local A1:", local_content["completed_rows"]["A1"])
        print("Remote A1:", remote_content["completed_rows"]["A1"])
        
        local_diff = self.sync.generate_diff("test.json", self.old_content, local_content, base_version=0)
        remote_diff = self.sync.generate_diff("test.json", self.old_content, remote_content, base_version=0)
        
        print("\nLocal diff changes:", local_diff.changes)
        print("Remote diff changes:", remote_diff.changes)
        
        # Check for conflicts before resolution
        conflicts = self.sync.detect_conflicts("test.json", local_diff, remote_diff)
        print("\nDetected conflicts before merge:", conflicts)
        
        # Resolve conflict by choosing local changes
        success, result = self.sync.merge_changes(
            "test.json",
            self.old_content,
            local_diff,
            remote_diff,
            {"completed_rows.A1": "local"}
        )
        
        print("\nMerge success:", success)
        print("Result A1:", result["completed_rows"]["A1"])
        
        self.assertTrue(success)
        self.assertEqual(result["completed_rows"]["A1"], [0, 1, 2, 3])

    def test_file_hash(self):
        """Test file content hash calculation."""
        hash1 = self.sync.calculate_file_hash(self.old_content)
        hash2 = self.sync.calculate_file_hash(deepcopy(self.old_content))
        hash3 = self.sync.calculate_file_hash(self.new_content)
        
        self.assertEqual(hash1, hash2)
        self.assertNotEqual(hash1, hash3)


if __name__ == '__main__':
    unittest.main()
