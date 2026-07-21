from kfchess.api.engine_config import EngineConfig
from kfchess.model.piece import PieceKind
from kfchess.realtime.cooldown import DEFAULT_JUMP_COOLDOWN_MS, DEFAULT_MOVE_COOLDOWN_MS
from kfchess.realtime.movement_profile import MOVE_DURATION_MS_PER_CELL
from kfchess.rules.scoring import points_for


class TestDefaults:
    def test_defaults_reproduce_the_hard_coded_engine_constants(self):
        config = EngineConfig()
        assert config.move_duration_ms_per_cell == MOVE_DURATION_MS_PER_CELL
        assert config.jump_duration_ms == MOVE_DURATION_MS_PER_CELL
        assert config.move_cooldown_ms == DEFAULT_MOVE_COOLDOWN_MS
        assert config.jump_cooldown_ms == DEFAULT_JUMP_COOLDOWN_MS
        for kind in PieceKind:
            assert config.point_values[kind] == points_for(kind)

    def test_is_frozen(self):
        config = EngineConfig()
        try:
            config.jump_duration_ms = 1
            assert False, "expected FrozenInstanceError"
        except Exception as exc:
            assert type(exc).__name__ == "FrozenInstanceError"

    def test_custom_values_override_defaults(self):
        config = EngineConfig(move_duration_ms_per_cell=250, point_values={PieceKind.PAWN: 42})
        assert config.move_duration_ms_per_cell == 250
        assert config.point_values == {PieceKind.PAWN: 42}
