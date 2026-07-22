from kfchess.model.game_state import GameState


class TestGameState:
    def test_defaults_to_not_game_over(self):
        assert GameState().game_over is False

    def test_game_over_is_mutable(self):
        state = GameState()
        state.game_over = True
        assert state.game_over is True

    def test_winner_defaults_to_none(self):
        assert GameState().winner is None

    def test_winner_is_mutable(self):
        state = GameState()
        state.winner = "w"
        assert state.winner == "w"

    def test_scores_default_to_zero_per_color(self):
        assert GameState().scores == {"w": 0, "b": 0}

    def test_add_score_accumulates_for_the_named_color(self):
        state = GameState()
        state.add_score("w", 5)
        state.add_score("w", 3)
        state.add_score("b", 1)
        assert state.scores == {"w": 8, "b": 1}

    def test_each_state_gets_its_own_scores_dict(self):
        first = GameState()
        first.add_score("w", 9)
        assert GameState().scores == {"w": 0, "b": 0}
