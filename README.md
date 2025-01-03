# NBT Mapart Helper

[![License: CC BY 4.0](https://img.shields.io/badge/License-CC_BY_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Version](https://img.shields.io/badge/version-0.2.1-blue.svg)]()

A Python tool for helping create Minecraft map art by analyzing NBT files block by block. Now with LAN collaboration support!

## Features

- View blocks organized by chunks
- Track progress of chunk completion
- Interactive row-by-row navigation mode
- Path completion for file selection
- Chunk statistics and analysis
- Save chunk data to files
- Configurable settings

### NEW: LAN Collaboration Features
- Work together with others on the same map art project
- Real-time synchronization of progress
- See who's working on which chunks
- Built-in chunk locking to prevent conflicts
- Host/client architecture for easy setup
- Automatic peer discovery on local network

## Installation

1. Clone the repository:
```bash
git clone https://github.com/voidfemme/nbt_mapart_helper.git
cd nbt_mapart_helper
```

2. Create and activate a virtual environment (recommended):
```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install the package in development mode:
```bash
pip install -e .
```

## Usage

1. Place your NBT file in the `resources` directory or specify a custom path in the config.

2. Run the helper:
```bash
python main.py
```

### Navigation

- Use the main menu to select different viewing modes
- In row-by-row mode:
  - Use 'n' and 'p' to navigate between rows
  - Enter a row number (0-15) to jump directly to that row
  - Use 'c' to mark a row as complete
  - Use 'u' to unmark a row
  - Use 'q' to return to the main menu

### LAN Mode

1. Enable LAN mode through the menu
2. One user should enable hosting mode
3. Other users on the network will automatically discover the host
4. Changes are automatically synchronized between all users
5. Users can see who is working on which chunks
6. Chunks are automatically locked when being edited

### Chunk Grid Legend

- `█` = Completed chunk
- `-` = Partially completed chunk
- `X` = Empty chunk

## Directory Structure

```
nbt_mapart_helper/
├── docs/           # Documentation
├── resources/      # Configuration and data files
├── src/           # Source code
│   ├── models/    # Data models
│   │   └── lan_session.py  # LAN functionality
│   ├── networking/   # Network communication
│   └── utils/     # Utility functions
└── tests/         # Test files
```

## Configuration

LAN-specific settings can be configured in `resources/config.json`:
- `lan_enabled`: Enable/disable LAN functionality
- `lan_port`: Port for network communication
- `lan_discovery_port`: Port for peer discovery
- `lan_auto_sync`: Enable/disable automatic synchronization
- `lan_sync_interval`: Time between automatic syncs (seconds)
- `lan_host_mode`: Whether this instance is acting as a host

## Contributing

Feel free to submit issues and pull requests.

## License

This project is licensed under the Creative Commons Attribution 4.0 International License - see the [LICENSE](LICENSE) file for details. This means you are free to:

- Share — copy and redistribute the material in any medium or format
- Adapt — remix, transform, and build upon the material for any purpose, even commercially

Under the following terms:
- Attribution — You must give appropriate credit, provide a link to the license, and indicate if changes were made.

For more information, visit: https://creativecommons.org/licenses/by/4.0/

