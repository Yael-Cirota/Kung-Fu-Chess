from kfchess.model.game_state import GameState


class TestGameState:
    def test_defaults_to_not_game_over(self):
        assert GameState().game_over is False

    def test_game_over_is_mutable(self):
        state = GameState()
        state.game_over = True
        assert state.game_over is True
