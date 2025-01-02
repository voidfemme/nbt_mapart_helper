"""Models for managing NBT chunk data."""

from collections import defaultdict
import string
from typing import Dict, List, Tuple, DefaultDict, Any


def get_chunk_reference(chunk_x: int, chunk_z: int) -> str:
    """Convert chunk coordinates to letter-number format (A1, B2, etc).

    Args:
        chunk_x: X coordinate of the chunk
        chunk_z: Z coordinate of the chunk

    Returns:
        String reference in format like 'A1'
    """
    letter = string.ascii_uppercase[chunk_z]
    number = chunk_x + 1
    return f"{letter}{number}"


def get_chunk_coordinates_from_reference(reference: str) -> Tuple[int, int]:
    """Convert reference (e.g., 'A1') back to chunk coordinates.

    Args:
        reference: Chunk reference string (e.g., 'A1')

    Returns:
        Tuple of (chunk_x, chunk_z) coordinates
    """
    letter = reference[0].upper()
    number = int(reference[1:])
    chunk_z = string.ascii_uppercase.index(letter)
    chunk_x = number - 1
    return chunk_x, chunk_z


class Block:
    """Represents a single block in the NBT structure."""

    def __init__(self, x: int, y: int, z: int, block_type: str):
        """Initialize a block.

        Args:
            x: Relative x coordinate within chunk
            y: Y coordinate
            z: Relative z coordinate within chunk
            block_type: Type of block (e.g., 'stone')
        """
        self.x = x
        self.y = y
        self.z = z
        self.block_type = block_type.replace("minecraft:", "")

    @property
    def relative_pos(self) -> Tuple[int, int, int]:
        """Get the relative position of the block within its chunk."""
        return (self.x, self.y, self.z)

    def to_dict(self) -> Dict[str, Any]:
        """Convert block to dictionary format."""
        return {"relative_pos": self.relative_pos, "block_type": self.block_type}


class Chunk:
    """Represents a 16x16 chunk of blocks."""

    def __init__(self, chunk_ref: str):
        """Initialize a chunk.

        Args:
            chunk_ref: Reference string for the chunk (e.g., 'A1')
        """
        self.chunk_ref = chunk_ref
        self.blocks_by_row: DefaultDict[int, List[Block]] = defaultdict(list)
        self.coordinates = get_chunk_coordinates_from_reference(chunk_ref)

    def add_block(self, block: Block) -> None:
        """Add a block to the chunk.

        Args:
            block: Block instance to add
        """
        self.blocks_by_row[block.z].append(block)

    def get_row(self, row_num: int) -> List[Block]:
        """Get all blocks in a specific row.

        Args:
            row_num: Row number to retrieve (0-15)

        Returns:
            List of blocks in the row
        """
        return sorted(self.blocks_by_row[row_num], key=lambda b: b.x)

    def to_dict(self) -> Dict[int, List[Dict]]:
        """Convert chunk data to dictionary format.

        Returns:
            Dictionary of row numbers to lists of block data
        """
        return {
            row: [block.to_dict() for block in blocks]
            for row, blocks in self.blocks_by_row.items()
        }


class ChunkManager:
    """Manages multiple chunks from an NBT file."""

    def __init__(self, nbt_file: Any):
        """Initialize chunk manager with NBT file data.

        Args:
            nbt_file: Parsed NBT file data
        """
        self.chunks: Dict[str, Chunk] = {}
        self._process_blocks(nbt_file)

    def _process_blocks(self, nbt_file: Any) -> None:
        """Process blocks from NBT file into chunks.

        Args:
            nbt_file: Parsed NBT file data
        """
        blocks = nbt_file.get("blocks", [])
        palette = nbt_file.get("palette", {})

        for block_data in blocks:
            pos = block_data["pos"]
            state = block_data["state"]
            x, y, z = [int(coord) for coord in pos]

            # Calculate chunk coordinates
            chunk_x, chunk_z = x // 16, z // 16
            chunk_ref = get_chunk_reference(chunk_x, chunk_z)

            # Calculate relative coordinates within chunk
            relative_x = x % 16
            relative_z = z % 16

            # Get block type from palette
            block_type = palette[state]["Name"]

            # Create or get chunk
            if chunk_ref not in self.chunks:
                self.chunks[chunk_ref] = Chunk(chunk_ref)

            # Create and add block
            block = Block(relative_x, y, relative_z, block_type)
            self.chunks[chunk_ref].add_block(block)

    def get_chunk(self, chunk_ref: str) -> Chunk:
        """Get a specific chunk by reference.

        Args:
            chunk_ref: Chunk reference string (e.g., 'A1')

        Returns:
            Chunk instance or None if not found
        """
        return self.chunks.get(chunk_ref)

    def list_chunks(self) -> List[str]:
        """Get list of all chunk references.

        Returns:
            List of chunk reference strings
        """
        return sorted(self.chunks.keys())

    def get_chunk_data(self, chunk_ref: str) -> Dict[int, List[Dict]]:
        """Get chunk data in dictionary format.

        Args:
            chunk_ref: Chunk reference string (e.g., 'A1')

        Returns:
            Dictionary of chunk data or None if chunk not found
        """
        chunk = self.get_chunk(chunk_ref)
        return chunk.to_dict() if chunk else None
