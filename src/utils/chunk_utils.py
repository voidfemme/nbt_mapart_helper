"""Utility functions for chunk analysis and processing."""

from collections import defaultdict
from typing import Dict, Any, DefaultDict


def get_chunk_statistics(
    chunk_data: Dict[int, list], chunk_ref: str, progress_tracker: Any
) -> Dict[str, Any]:
    """Calculate statistics for a chunk.

    Args:
        chunk_data: Dictionary of chunk data indexed by row number
        chunk_ref: Reference identifier for the chunk (e.g., 'A1')
        progress_tracker: Progress tracking object

    Returns:
        Dictionary containing various statistics about the chunk
    """
    if not chunk_data:
        return "Chunk not found!"

    stats = {
        "total_blocks": 0,
        "block_types": defaultdict(int),
        "rows_complete": len(progress_tracker.get_completed_rows(chunk_ref)),
        "is_chunk_complete": chunk_ref in progress_tracker.progress["completed_chunks"],
        "last_modified": progress_tracker.progress["last_modified"].get(
            chunk_ref, "Never"
        ),
        "max_height": float("-inf"),
        "max_height_block": None,
        "min_height": float("inf"),
        "min_height_block": None,
        "unique_block_types": 0,
        "most_common_block": None,
        "most_common_count": 0,
        "blocks_per_row": defaultdict(int),
    }

    # Process each row in the chunk
    for z, blocks in chunk_data.items():
        row_block_count = len(blocks)
        stats["blocks_per_row"][z] = row_block_count
        stats["total_blocks"] += row_block_count

        # Process each block in the row
        for block in blocks:
            block_type = block["block_type"]
            x, y, z = block["relative_pos"]

            # Update block type counts
            stats["block_types"][block_type] += 1

            # Track height records
            if y > stats["max_height"]:
                stats["max_height"] = y
                stats["max_height_block"] = block_type
            if y < stats["min_height"]:
                stats["min_height"] = y
                stats["min_height_block"] = block_type

            # Update most common block
            if stats["block_types"][block_type] > stats["most_common_count"]:
                stats["most_common_count"] = stats["block_types"][block_type]
                stats["most_common_block"] = block_type

    # Calculate final statistics
    stats["unique_block_types"] = len(stats["block_types"])

    # Find densest and sparsest rows
    if stats["blocks_per_row"]:
        stats["densest_row"] = max(stats["blocks_per_row"].items(), key=lambda x: x[1])[
            0
        ]
        stats["sparsest_row"] = min(
            stats["blocks_per_row"].items(), key=lambda x: x[1]
        )[0]

    return stats


def save_chunk_data(chunk_data: Dict[str, Any], filename: str) -> str:
    """Save chunk data to a file.

    Args:
        chunk_data: The chunk data to save
        filename: Path to the output file

    Returns:
        Message indicating success or failure
    """
    try:
        with open(filename, "w") as f:
            f.write(chunk_data)
        return f"Data saved to {filename}"
    except Exception as e:
        return f"Error saving data: {str(e)}"


def get_block_requirements(
    block_types: DefaultDict[str, int]
) -> Dict[str, Dict[str, int]]:
    """Calculate block requirements from block type counts.

    Args:
        block_types: Dictionary of block types and their counts

    Returns:
        Dictionary containing block requirements (total, stacks, extras)
    """
    requirements = {}
    for block_type, count in block_types.items():
        stacks = count // 64
        extras = count % 64
        requirements[block_type] = {
            "total": count,
            "stacks": stacks if stacks > 0 else 0,
            "extras": extras if count >= 64 else count,
        }
    return requirements
