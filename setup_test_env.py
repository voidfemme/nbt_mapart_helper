#!/usr/bin/env python3
"""Set up test environment for NBT Mapart Helper."""

import os
import json
import shutil
from pathlib import Path

# Base configuration
BASE_CONFIG = {
    "nbt_file": "resources/David_0_0.nbt",
    "progress_file": "resources/progress.json",
    "output_directory": "resources/output",
    "backup_directory": "resources/backups",
    "auto_save": True,
    "auto_backup": False,
    "backup_interval": 3600,
    "lan_enabled": True,
    "lan_auto_sync": True,
    "lan_sync_interval": 300,
}

def create_test_environment():
    """Create test environment with two separate instances."""
    # Create base directories
    base_dir = Path("test_environment")
    if base_dir.exists():
        shutil.rmtree(base_dir)
    base_dir.mkdir()

    # Create instance directories
    for instance in ["instance1", "instance2"]:
        instance_dir = base_dir / instance
        resources_dir = instance_dir / "resources"
        
        # Create directory structure
        for subdir in ["output", "backups"]:
            (resources_dir / subdir).mkdir(parents=True)

        # Create config for this instance
        config = BASE_CONFIG.copy()
        if instance == "instance1":
            config.update({
                "lan_port": 8080,
                "lan_discovery_port": 8081,
                "lan_host_mode": True
            })
        else:
            config.update({
                "lan_port": 8082,
                "lan_discovery_port": 8083,
                "lan_host_mode": False
            })

        # Update paths to be relative to instance directory
        for key in ["nbt_file", "progress_file", "output_directory", "backup_directory"]:
            config[key] = str(Path("resources") / os.path.basename(config[key]))

        # Save config
        with open(resources_dir / "config.json", "w") as f:
            json.dump(config, f, indent=4)

        # Create empty progress and session files
        with open(resources_dir / "progress.json", "w") as f:
            json.dump({"completed_rows": {}, "completed_chunks": [], "last_modified": {}}, f, indent=4)

        with open(resources_dir / "sessions.json", "w") as f:
            json.dump({"chunk_locks": {}, "active_users": {}}, f, indent=4)

        # Create sample NBT file (for testing)
        with open(resources_dir / "David_0_0.nbt", "w") as f:
            f.write("Sample NBT data")

    print("Test environment created successfully!")
    print("\nTo run the instances:")
    print("1. Open two terminal windows")
    print("2. In terminal 1:")
    print("   cd test_environment/instance1")
    print("   python ../../main.py")
    print("3. In terminal 2:")
    print("   cd test_environment/instance2")
    print("   python ../../main.py")

if __name__ == "__main__":
    create_test_environment()
