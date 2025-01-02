# NBT Viewer

A Python tool for viewing and analyzing NBT file blocks in a chunk-based format.

## Features

- View blocks organized by chunks
- Track progress of chunk completion
- Interactive row-by-row navigation mode
- Path completion for file selection
- Chunk statistics and analysis
- Save chunk data to files
- Configurable settings

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/nbt-viewer.git
cd nbt-viewer
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

2. Run the viewer:
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

### Chunk Grid Legend

- █ = Completed chunk
- - = Partially completed chunk
- X = Empty chunk

## Directory Structure

```
nbt_viewer/
├── docs/           # Documentation
├── resources/      # Configuration and data files
├── src/           # Source code
│   ├── models/    # Data models
│   └── utils/     # Utility functions
└── tests/         # Test files
```

## Contributing

Feel free to submit issues and pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
