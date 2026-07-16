"""
Engine -> DTO translation, isolated from the adapter.

This is the one place that knows how a live kfchess.model.Piece / motion
object maps onto the outward-facing DTOs (attribute renames, enum-value
extraction, grid traversal). EngineGameSession delegates to the engine and
hands the raw results here, so it stays a thin adapter with no knowledge of
these engine internals.
"""

from kfchess.api.dto import BoardSnapshot, MotionInfo, MoveLogEntry, PieceView


def piece_to_view(piece) -> PieceView:
    return PieceView(
        piece_id=piece.piece_id,
        symbol=piece.get_symbol(),
        color=piece.color.value,
        cell=piece.cell,
    )


def motion_to_info(motion) -> MotionInfo:
    return MotionInfo(
        from_pos=motion.origin,
        to_pos=motion.target,
        start_ms=motion.started_at_ms,
        duration_ms=motion.total_duration_ms,
        is_jump=motion.is_jump,
    )


def move_record_to_entry(record) -> MoveLogEntry:
    return MoveLogEntry(
        color=record.color,
        symbol=record.symbol,
        from_pos=record.from_pos,
        to_pos=record.to_pos,
    )


def snapshot_from_grid(grid) -> BoardSnapshot:
    rows = len(grid)
    cols = len(grid[0]) if grid else 0
    piece_views = [piece_to_view(piece) for row in grid for piece in row if piece is not None]
    return BoardSnapshot(rows=rows, cols=cols, piece_views=piece_views)


def find_piece_by_id(grid, piece_id: int):
    for row in grid:
        for piece in row:
            if piece is not None and piece.piece_id == piece_id:
                return piece
    return None
