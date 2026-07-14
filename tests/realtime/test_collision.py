from kfchess.model.piece import Piece, PieceKind
from kfchess.realtime.collision import (
    CollisionType, ResolutionAction, CollisionDetector, CollisionResolver,
    ProceedResolution, StopResolution, CaptureResolution, DEFAULT_RESOLUTIONS,
)


class TestCollisionDetector:
    def setup_method(self):
        self.detector = CollisionDetector()
        self.mover = Piece('w', PieceKind.ROOK)

    def test_empty_square_is_no_collision(self):
        assert self.detector.classify(self.mover, None) is CollisionType.NONE

    def test_same_colour_occupant_is_a_same_colour_collision(self):
        friend = Piece('w', PieceKind.PAWN)
        assert self.detector.classify(self.mover, friend) is CollisionType.SAME_COLOR

    def test_opposite_colour_occupant_is_a_different_colour_collision(self):
        enemy = Piece('b', PieceKind.PAWN)
        assert self.detector.classify(self.mover, enemy) is CollisionType.DIFFERENT_COLOR


class TestCollisionResolver:
    def setup_method(self):
        self.resolver = CollisionResolver()
        self.mover = Piece('w', PieceKind.ROOK)

    def test_no_collision_proceeds(self):
        resolution = self.resolver.resolve(CollisionType.NONE, self.mover, None)
        assert resolution.action is ResolutionAction.PROCEED
        assert resolution.captured_piece is None

    def test_same_colour_stops(self):
        friend = Piece('w', PieceKind.PAWN)
        resolution = self.resolver.resolve(CollisionType.SAME_COLOR, self.mover, friend)
        assert resolution.action is ResolutionAction.STOP
        assert resolution.captured_piece is None

    def test_different_colour_captures_the_occupant(self):
        enemy = Piece('b', PieceKind.PAWN)
        resolution = self.resolver.resolve(CollisionType.DIFFERENT_COLOR, self.mover, enemy)
        assert resolution.action is ResolutionAction.CAPTURE
        assert resolution.captured_piece is enemy

    def test_default_resolution_table_covers_every_collision_type(self):
        assert set(DEFAULT_RESOLUTIONS) == set(CollisionType)
        assert isinstance(DEFAULT_RESOLUTIONS[CollisionType.NONE], ProceedResolution)
        assert isinstance(DEFAULT_RESOLUTIONS[CollisionType.SAME_COLOR], StopResolution)
        assert isinstance(DEFAULT_RESOLUTIONS[CollisionType.DIFFERENT_COLOR], CaptureResolution)

    def test_a_custom_strategy_table_can_be_injected(self):
        # Different-colour collisions made non-lethal (proceed, don't capture).
        resolver = CollisionResolver(resolutions={
            CollisionType.NONE: ProceedResolution(),
            CollisionType.SAME_COLOR: StopResolution(),
            CollisionType.DIFFERENT_COLOR: ProceedResolution(),
        })
        enemy = Piece('b', PieceKind.PAWN)
        resolution = resolver.resolve(CollisionType.DIFFERENT_COLOR, self.mover, enemy)
        assert resolution.action is ResolutionAction.PROCEED
