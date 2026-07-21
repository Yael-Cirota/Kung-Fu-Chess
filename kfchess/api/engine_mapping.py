"""
Engine -> DTO translation, isolated from the adapter.

This is the one place that knows how a live kfchess.model.Piece / motion
object maps onto the outward-facing DTOs (attribute renames, enum-value
extraction, grid traversal). EngineGameSession delegates to the engine and
hands the raw results here, so it stays a thin adapter with no knowledge of
these engine internals.
"""

from kfchess.api.dto import BoardSnapshot, MotionInfo, MoveLogEntry, PieceView, Scoreboard
from kfchess.api.events import EngineEvent, EngineEventKind
from kfchess.model.piece import Color
from kfchess.realtime.motion import MoveOutcomeStatus


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


def scoreboard_from_scores(scores) -> Scoreboard:
    return Scoreboard(white=scores.get(Color.WHITE.value, 0), black=scores.get(Color.BLACK.value, 0))


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


def outcome_to_event(outcome, at_ms: int) -> EngineEvent:
    """
    Maps a realtime MoveOutcome onto the outward-facing EngineEvent DTO.
    Mirrors the beneficiary inversion in GameEngine._scoring_capture: an
    EXECUTED outcome credits its own piece's color, while a
    CAPTURED_ON_ARRIVAL outcome credits the *other* color, since the
    outcome's own piece is the one that got taken.
    """
    piece_view = piece_to_view(outcome.piece)

    if outcome.status is MoveOutcomeStatus.ABORTED_PREMOVE:
        kind = EngineEventKind.MOVE_ABORTED
        captured, beneficiary_color = None, None
    elif outcome.status is MoveOutcomeStatus.STOPPED_BY_FRIENDLY:
        kind = EngineEventKind.MOVE_STOPPED
        captured, beneficiary_color = None, None
    elif outcome.status is MoveOutcomeStatus.CAPTURED_ON_ARRIVAL:
        kind = EngineEventKind.PIECE_CAPTURED
        captured = piece_view
        beneficiary_color = outcome.piece.color.opponent().value
    elif outcome.captured_piece is not None:
        kind = EngineEventKind.PIECE_CAPTURED
        captured = piece_to_view(outcome.captured_piece)
        beneficiary_color = outcome.piece.color.value
    else:
        kind = EngineEventKind.MOVE_EXECUTED
        captured, beneficiary_color = None, None

    return EngineEvent(
        kind=kind,
        at_ms=at_ms,
        piece=piece_view,
        from_pos=outcome.from_pos,
        to_pos=outcome.to_pos,
        captured=captured,
        beneficiary_color=beneficiary_color,
    )
