from kfchess.model.piece import PieceKind
from kfchess.model.position import Position
from kfchess.realtime.movement_profile import (
    SlidingProfile, JumpingProfile, DEFAULT_MOVEMENT_PROFILES, MOVE_DURATION_MS_PER_CELL,
)


class TestSlidingProfile:
    def test_horizontal_path_lists_every_square_excluding_origin(self):
        profile = SlidingProfile()
        path = profile.occupied_path(Position(0, 0), Position(0, 3))
        assert path == [Position(0, 1), Position(0, 2), Position(0, 3)]

    def test_diagonal_path_steps_one_cell_on_each_axis(self):
        profile = SlidingProfile()
        path = profile.occupied_path(Position(2, 2), Position(5, 5))
        assert path == [Position(3, 3), Position(4, 4), Position(5, 5)]

    def test_backward_direction_is_handled(self):
        profile = SlidingProfile()
        path = profile.occupied_path(Position(5, 5), Position(2, 5))
        assert path == [Position(4, 5), Position(3, 5), Position(2, 5)]

    def test_single_square_path_is_just_the_destination(self):
        profile = SlidingProfile()
        assert profile.occupied_path(Position(4, 4), Position(4, 5)) == [Position(4, 5)]

    def test_step_duration_is_one_cell(self):
        profile = SlidingProfile()
        assert profile.step_duration_ms(Position(0, 0), Position(0, 7)) == MOVE_DURATION_MS_PER_CELL


class TestJumpingProfile:
    def test_path_is_only_the_destination(self):
        profile = JumpingProfile()
        assert profile.occupied_path(Position(4, 4), Position(6, 5)) == [Position(6, 5)]

    def test_step_duration_spans_the_whole_chebyshev_distance(self):
        profile = JumpingProfile()
        # Knight L-move: max axis is 2, so the single hop lasts two cells.
        assert profile.step_duration_ms(Position(4, 4), Position(6, 5)) == 2 * MOVE_DURATION_MS_PER_CELL


class TestDefaultProfiles:
    def test_sliders_use_the_sliding_profile(self):
        for kind in (PieceKind.ROOK, PieceKind.BISHOP, PieceKind.QUEEN, PieceKind.KING, PieceKind.PAWN):
            assert isinstance(DEFAULT_MOVEMENT_PROFILES[kind], SlidingProfile)

    def test_knight_uses_the_jumping_profile(self):
        assert isinstance(DEFAULT_MOVEMENT_PROFILES[PieceKind.KNIGHT], JumpingProfile)
