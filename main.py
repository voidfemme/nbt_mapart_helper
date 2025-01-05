"""Entry point for NBT Mapart Helper application."""

import sys
from src.application import NBTViewer


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
