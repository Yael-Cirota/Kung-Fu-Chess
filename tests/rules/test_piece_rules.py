from kfchess.model.piece import Piece, PieceKind
from kfchess.model.board import Board
from kfchess.model.position import Position
from kfchess.rules.piece_rules import (
    RookRule, BishopRule, QueenRule, KnightRule, KingRule, PawnRule,
)


def empty_grid(rows=8, cols=8):
    return [[None] * cols for _ in range(rows)]


def board_with(*pieces_at, rows=8, cols=8):
    grid = empty_grid(rows, cols)
    for (row, col), piece in pieces_at:
        grid[row][col] = piece
    return Board(grid)


class TestRookRule:
    def test_moves_along_empty_rank_and_file(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((4, 4), rook))

        destinations = RookRule.legal_destinations(board, rook)

        for col in range(8):
            if col != 4:
                assert Position(4, col) in destinations
        for row in range(8):
            if row != 4:
                assert Position(row, 4) in destinations
        assert Position(0, 0) not in destinations
        assert Position(7, 7) not in destinations

    def test_reaches_through_and_past_occupants_because_occupancy_is_ignored(self):
        # Pattern-only geometry: a blocker (friendly or enemy) neither
        # stops the ray nor is excluded - collisions are resolved in flight.
        rook = Piece('w', PieceKind.ROOK)
        friendly = Piece('w', PieceKind.ROOK)
        enemy = Piece('b', PieceKind.ROOK)
        board = board_with(((4, 0), rook), ((4, 3), friendly), ((4, 6), enemy))

        destinations = RookRule.legal_destinations(board, rook)

        for col in range(1, 8):
            assert Position(4, col) in destinations

    def test_does_not_mutate_board_or_pieces(self):
        rook = Piece('w', PieceKind.ROOK)
        enemy = Piece('b', PieceKind.ROOK)
        board = board_with(((4, 0), rook), ((4, 3), enemy))

        RookRule.legal_destinations(board, rook)

        assert board.get(Position(4, 0)) is rook
        assert board.get(Position(4, 3)) is enemy


class TestBishopRule:
    def test_moves_diagonally_not_straight(self):
        bishop = Piece('w', PieceKind.BISHOP)
        board = board_with(((4, 4), bishop))

        destinations = BishopRule.legal_destinations(board, bishop)

        assert Position(3, 3) in destinations
        assert Position(0, 0) in destinations
        assert Position(6, 6) in destinations
        assert Position(1, 7) in destinations
        assert Position(4, 5) not in destinations
        assert Position(3, 4) not in destinations

    def test_reaches_through_and_past_diagonal_occupants(self):
        bishop = Piece('w', PieceKind.BISHOP)
        friendly = Piece('w', PieceKind.BISHOP)
        board = board_with(((0, 0), bishop), ((3, 3), friendly))

        destinations = BishopRule.legal_destinations(board, bishop)

        assert Position(2, 2) in destinations
        assert Position(3, 3) in destinations
        assert Position(4, 4) in destinations


class TestQueenRule:
    def test_combines_rook_and_bishop_movement(self):
        queen = Piece('w', PieceKind.QUEEN)
        board = board_with(((4, 4), queen))

        destinations = QueenRule.legal_destinations(board, queen)

        assert Position(4, 7) in destinations
        assert Position(0, 4) in destinations
        assert Position(0, 0) in destinations
        assert Position(7, 7) in destinations
        assert Position(6, 5) not in destinations

    def test_reaches_through_occupants_on_diagonal_and_rank(self):
        queen = Piece('w', PieceKind.QUEEN)
        friendly = Piece('w', PieceKind.QUEEN)
        enemy = Piece('b', PieceKind.QUEEN)
        board = board_with(((0, 0), queen), ((3, 3), friendly), ((0, 4), enemy))

        destinations = QueenRule.legal_destinations(board, queen)

        assert Position(2, 2) in destinations
        assert Position(3, 3) in destinations
        assert Position(4, 4) in destinations
        assert Position(0, 4) in destinations
        assert Position(0, 7) in destinations


class TestKnightRule:
    def test_l_shape_jumps(self):
        knight = Piece('w', PieceKind.KNIGHT)
        board = board_with(((4, 4), knight))

        destinations = KnightRule.legal_destinations(board, knight)

        for dr, dc in [(2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2)]:
            assert Position(4 + dr, 4 + dc) in destinations
        assert Position(4, 5) not in destinations
        assert Position(5, 5) not in destinations

    def test_jumps_over_blocking_pieces(self):
        knight = Piece('w', PieceKind.KNIGHT)
        blocker_a = Piece('b', PieceKind.ROOK)
        blocker_b = Piece('b', PieceKind.ROOK)
        board = board_with(((4, 4), knight), ((4, 5), blocker_a), ((5, 4), blocker_b))

        destinations = KnightRule.legal_destinations(board, knight)

        assert Position(6, 5) in destinations
        assert Position(5, 6) in destinations

    def test_includes_friendly_occupied_landing_square_occupancy_is_ignored(self):
        knight = Piece('w', PieceKind.KNIGHT)
        friendly = Piece('w', PieceKind.ROOK)
        board = board_with(((4, 4), knight), ((6, 5), friendly))

        destinations = KnightRule.legal_destinations(board, knight)

        assert Position(6, 5) in destinations

    def test_includes_enemy_occupied_landing_square(self):
        knight = Piece('w', PieceKind.KNIGHT)
        enemy = Piece('b', PieceKind.ROOK)
        board = board_with(((4, 4), knight), ((6, 5), enemy))

        destinations = KnightRule.legal_destinations(board, knight)

        assert Position(6, 5) in destinations


class TestKingRule:
    def test_moves_strictly_one_square(self):
        king = Piece('w', PieceKind.KING)
        board = board_with(((4, 4), king))

        destinations = KingRule.legal_destinations(board, king)

        expected = {
            Position(3, 3), Position(3, 4), Position(3, 5),
            Position(4, 3), Position(4, 5),
            Position(5, 3), Position(5, 4), Position(5, 5),
        }
        assert destinations == expected

    def test_includes_friendly_occupied_squares_occupancy_is_ignored(self):
        king = Piece('w', PieceKind.KING)
        friendly = Piece('w', PieceKind.ROOK)
        board = board_with(((4, 4), king), ((4, 5), friendly))

        destinations = KingRule.legal_destinations(board, king)

        assert Position(4, 5) in destinations

    def test_includes_enemy_occupied_squares(self):
        king = Piece('w', PieceKind.KING)
        enemy = Piece('b', PieceKind.ROOK)
        board = board_with(((4, 4), king), ((4, 5), enemy))

        destinations = KingRule.legal_destinations(board, king)

        assert Position(4, 5) in destinations

    def test_corner_king_has_only_three_destinations(self):
        king = Piece('w', PieceKind.KING)
        board = board_with(((0, 0), king))

        destinations = KingRule.legal_destinations(board, king)

        assert destinations == {Position(0, 1), Position(1, 0), Position(1, 1)}


class TestPawnRule:
    def test_white_pawn_moves_one_square_up(self):
        pawn = Piece('w', PieceKind.PAWN)
        board = board_with(((4, 3), pawn))

        destinations = PawnRule.legal_destinations(board, pawn)

        assert Position(3, 3) in destinations

    def test_black_pawn_moves_one_square_down(self):
        pawn = Piece('b', PieceKind.PAWN)
        board = board_with(((3, 3), pawn))

        destinations = PawnRule.legal_destinations(board, pawn)

        assert Position(4, 3) in destinations

    def test_blocked_forward_square_excluded(self):
        pawn = Piece('w', PieceKind.PAWN)
        blocker = Piece('b', PieceKind.PAWN)
        board = board_with(((4, 3), pawn), ((3, 3), blocker))

        destinations = PawnRule.legal_destinations(board, pawn)

        assert Position(3, 3) not in destinations

    def test_captures_diagonally(self):
        pawn = Piece('w', PieceKind.PAWN)
        left_enemy = Piece('b', PieceKind.PAWN)
        right_enemy = Piece('b', PieceKind.PAWN)
        board = board_with(((4, 3), pawn), ((3, 2), left_enemy), ((3, 4), right_enemy))

        destinations = PawnRule.legal_destinations(board, pawn)

        assert Position(3, 2) in destinations
        assert Position(3, 4) in destinations

    def test_cannot_capture_forward(self):
        pawn = Piece('w', PieceKind.PAWN)
        enemy = Piece('b', PieceKind.PAWN)
        board = board_with(((4, 3), pawn), ((3, 3), enemy))

        destinations = PawnRule.legal_destinations(board, pawn)

        assert Position(3, 3) not in destinations

    def test_cannot_capture_friendly_diagonally(self):
        pawn = Piece('w', PieceKind.PAWN)
        friendly = Piece('w', PieceKind.PAWN)
        board = board_with(((4, 3), pawn), ((3, 4), friendly))

        destinations = PawnRule.legal_destinations(board, pawn)

        assert Position(3, 4) not in destinations

    def test_no_diagonal_move_without_a_capture(self):
        pawn = Piece('w', PieceKind.PAWN)
        board = board_with(((4, 3), pawn))

        destinations = PawnRule.legal_destinations(board, pawn)

        assert Position(3, 2) not in destinations
        assert Position(3, 4) not in destinations

    def test_double_step_allowed_from_start_row(self):
        pawn = Piece('w', PieceKind.PAWN)
        board = board_with(((6, 3), pawn))

        destinations = PawnRule.legal_destinations(board, pawn)

        assert Position(4, 3) in destinations
        assert Position(5, 3) in destinations

    def test_no_double_step_once_pawn_has_moved(self):
        pawn = Piece('w', PieceKind.PAWN)
        pawn.has_moved = True
        board = board_with(((6, 3), pawn))

        destinations = PawnRule.legal_destinations(board, pawn)

        assert Position(4, 3) not in destinations
        assert Position(5, 3) in destinations

    def test_no_double_step_when_not_on_start_row(self):
        pawn = Piece('w', PieceKind.PAWN)
        board = board_with(((4, 3), pawn))

        destinations = PawnRule.legal_destinations(board, pawn)

        assert Position(2, 3) not in destinations
        assert Position(3, 3) in destinations

    def test_double_step_blocked_by_piece_two_squares_ahead(self):
        pawn = Piece('w', PieceKind.PAWN)
        blocker = Piece('b', PieceKind.PAWN)
        board = board_with(((6, 3), pawn), ((4, 3), blocker))

        destinations = PawnRule.legal_destinations(board, pawn)

        assert Position(4, 3) not in destinations
        assert Position(5, 3) in destinations

    def test_double_step_blocked_by_piece_one_square_ahead(self):
        pawn = Piece('w', PieceKind.PAWN)
        blocker = Piece('b', PieceKind.PAWN)
        board = board_with(((6, 3), pawn), ((5, 3), blocker))

        destinations = PawnRule.legal_destinations(board, pawn)

        assert Position(4, 3) not in destinations
        assert Position(5, 3) not in destinations

    def test_cannot_move_backward(self):
        pawn = Piece('w', PieceKind.PAWN)
        board = board_with(((4, 3), pawn))

        destinations = PawnRule.legal_destinations(board, pawn)

        assert Position(5, 3) not in destinations
