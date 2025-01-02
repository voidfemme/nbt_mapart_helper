"""Path completion utilities for command-line interface."""
import gnureadline as readline
import glob
import os


class PathCompleter:
    """Provides tab completion for file paths in command line input."""
    
    def __init__(self):
        """Initialize the path completer."""
        self.matches = []

    def complete(self, text, state):
        """Return the state'th completion for text.
        
        Args:
            text (str): The text to complete
            state (int): The state of the completion (0 for first match, 1 for second, etc.)
            
        Returns:
            str: The completion match, or None if no match found
        """
        if state == 0:
            # Handle home directory expansion
            if "~" in text:
                text = os.path.expanduser(text)

            # Add trailing slash to directory names
            if os.path.isdir(text):
                text += "/"

            # Find all matching files/directories
            if os.path.isdir(os.path.dirname(text)):
                self.matches = glob.glob(text + "*")
            else:
                self.matches = glob.glob(text + "*")

            # Add trailing slash to directory matches
            if len(self.matches) == 1 and os.path.isdir(self.matches[0]):
                self.matches[0] += "/"

        try:
            return self.matches[state]
        except IndexError:
            return None


def setup_path_completion():
    """Set up tab completion for file paths."""
    readline.set_completer_delims(" \t\n;")
    readline.parse_and_bind("tab: complete")
    readline.set_completer(PathCompleter().complete)


def input_with_path_completion(prompt):
    """Get input with path completion enabled.
    
    Args:
        prompt (str): The input prompt to display
        
    Returns:
        str: The user's input with whitespace stripped
    """
    setup_path_completion()
    try:
        return input(prompt).strip()
    finally:
        # Reset the completer to avoid affecting other readline operations
        readline.set_completer(None)
