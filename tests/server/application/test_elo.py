from server.application.elo import EloCalculator


class TestEqualRatings:
    def test_winner_gains_half_k_and_loser_loses_half_k(self):
        calculator = EloCalculator(k_factor=32)
        new_winner, new_loser = calculator.updated(1200, 1200)

        assert new_winner == 1216
        assert new_loser == 1184


class TestUnderdogWins:
    def test_lower_rated_winner_gains_more_than_half_k(self):
        calculator = EloCalculator(k_factor=32)
        new_winner, new_loser = calculator.updated(1000, 1400)

        assert new_winner - 1000 > 16
        assert 1400 - new_loser > 16


class TestFavoriteWins:
    def test_higher_rated_winner_gains_less_than_half_k(self):
        calculator = EloCalculator(k_factor=32)
        new_winner, new_loser = calculator.updated(1400, 1000)

        assert new_winner - 1400 < 16
        assert 1000 - new_loser < 16


class TestCustomKFactor:
    def test_smaller_k_factor_produces_smaller_swings(self):
        big_k = EloCalculator(k_factor=32).updated(1200, 1200)
        small_k = EloCalculator(k_factor=16).updated(1200, 1200)

        assert (big_k[0] - 1200) > (small_k[0] - 1200)
