from kfchess.model.piece import PieceKind
from kfchess.rules.scoring import POINT_VALUES, ScoringPolicy, points_for


class TestPointValues:
    def test_standard_material_values(self):
        assert points_for(PieceKind.PAWN) == 1
        assert points_for(PieceKind.KNIGHT) == 3
        assert points_for(PieceKind.BISHOP) == 3
        assert points_for(PieceKind.ROOK) == 5
        assert points_for(PieceKind.QUEEN) == 9

    def test_king_is_worth_ten(self):
        assert points_for(PieceKind.KING) == 10

    def test_every_kind_has_a_value(self):
        assert set(POINT_VALUES) == set(PieceKind)


class TestScoringPolicy:
    def test_default_policy_matches_the_module_level_point_values(self):
        policy = ScoringPolicy()
        for kind in PieceKind:
            assert policy.points_for(kind) == points_for(kind)

    def test_custom_point_values_override_the_defaults(self):
        policy = ScoringPolicy(point_values={PieceKind.PAWN: 100})
        assert policy.points_for(PieceKind.PAWN) == 100
