"""Formatting utilities for chunk data display."""
from typing import Dict, List, Any
import string


def format_chunk_statistics(stats: Dict[str, Any]) -> str:
    """Format chunk statistics into a readable string.
    
    Args:
        stats: Dictionary containing chunk statistics
        
    Returns:
        Formatted string containing statistics
    """
    output = ["\nChunk Statistics:"]
    output.append(f"Total blocks: {stats['total_blocks']}")
    output.append(f"Rows completed: {stats['rows_complete']}/16")
    output.append(
        f"Chunk status: {'Complete' if stats['is_chunk_complete'] else 'In Progress'}"
    )
    
    output.append(f"\nHeight Information:")
    output.append(
        f"Highest block: {stats['max_height_block']} at Y={stats['max_height']}"
    )
    output.append(
        f"Lowest block: {stats['min_height_block']} at Y={stats['min_height']}"
    )
    
    output.append(f"\nBlock Distribution:")
    output.append(f"Unique block types: {stats['unique_block_types']}")
    output.append(
        f"Most common block: {stats['most_common_block']} ({stats['most_common_count']} blocks)"
    )

    # Add block requirements table
    output.append("\nBlock Requirements:")
    header = "{:<25} {:>8} {:>8} {:>8}".format("Block Type", "Total", "Stacks", "Extra")
    separator = "-" * 52
    output.append(separator)
    output.append(header)
    output.append(separator)

    for block_type, count in sorted(stats["block_types"].items()):
        stacks = count // 64
        extras = count % 64
        output.append(
            "{:<25} {:>8} {:>8} {:>8}".format(
                block_type,
                count,
                stacks if stacks > 0 else "-",
                extras if count >= 64 else count,
            )
        )

    output.append(separator)
    output.append(f"\nLast modified: {stats['last_modified']}")

    return "\n".join(output)


def format_row_data(chunk_data: Dict[int, List[Dict]], chunk_ref: str, row_num: int, completed: bool) -> str:
    """Format data for a single row of blocks.
    
    Args:
        chunk_data: Dictionary containing row data
        row_num: Row number to format
        completed: Whether the row is marked as complete
        
    Returns:
        Formatted string containing row data
    """
    output = []
    table_header = "\n{:^25} {:^4} {:^4} {:^4} {:^10}".format(
        "Block Type", "x", "z", "y", "Status"
    )
    table_separator = "-" * 50

    output.append(f"\nChunk {chunk_ref}, Row {row_num}: {'[COMPLETED]' if completed else ''}")
    output.append(table_header)
    output.append(table_separator)

    row_blocks = []
    blocks = chunk_data[row_num]
    for block in blocks:
        rx, y, rz = block["relative_pos"]
        row_blocks.append({"x": rx, "y": y, "z": rz, "type": block["block_type"]})

    # Sort blocks by x coordinate for consistent display
    row_blocks.sort(key=lambda b: b["x"])

    for block in row_blocks:
        output.append(
            "{:<25} {:>4} {:>4} {:>4} {:^10}".format(
                block["type"],
                block["x"],
                block["z"],
                block["y"],
                "Done" if completed else "",
            )
        )

    return "\n".join(output)


def format_chunk_grid(chunks: Dict[str, Any], progress_tracker: 'ProgressTracker') -> str:
    """Format available chunks in a grid format with completion status.
    
    Args:
        chunks: Dictionary of available chunks
        progress_tracker: Progress tracking instance to check completion status
        
    Returns:
        Formatted string showing chunk grid
    """
    if not chunks:
        return "No chunks found!"

    # Find the range of chunk coordinates
    max_letter = max(ref[0] for ref in chunks.keys())
    max_number = max(int(ref[1:]) for ref in chunks.keys())

    # Create the grid
    output = ["\nAvailable Chunks Grid:"]
    output.append("\nLegend:")
    output.append("█ = Completed chunk")
    output.append("- = Partially completed chunk")
    output.append("X = Empty chunk\n")
    
    output.append("   " + " ".join(f"{i:2}" for i in range(1, max_number + 1)))
    output.append("   " + "-" * (max_number * 3))

    for letter in string.ascii_uppercase[
        : string.ascii_uppercase.index(max_letter) + 1
    ]:
        row = [f"{letter} |"]
        for number in range(1, max_number + 1):
            chunk_ref = f"{letter}{number}"
            if chunk_ref in chunks:
                if progress_tracker.is_chunk_complete(chunk_ref):
                    row.append(" █ ")
                elif len(progress_tracker.get_completed_rows(chunk_ref)) > 0:
                    row.append(" - ")
                else:
                    row.append(" X ")
            else:
                row.append("   ")
        output.append("".join(row))

    return "\n".join(output)
