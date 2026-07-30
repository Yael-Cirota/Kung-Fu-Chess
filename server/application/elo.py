from typing import Tuple

# Rating gap that corresponds to ODDS_PER_SCALE:1 odds in favour of the
# higher-rated player. Together these define the logistic expected-score curve.
RATING_SCALE = 400
ODDS_PER_SCALE = 10

# Actual score of a game, as fed into the Elo update.
WIN = 1.0
LOSS = 0.0


class EloCalculator:
    def __init__(self, k_factor: int = 32):
        self._k = k_factor

    def updated(self, winner_elo: int, loser_elo: int) -> Tuple[int, int]:
        gap = loser_elo - winner_elo
        expected_winner = 1 / (1 + ODDS_PER_SCALE ** (gap / RATING_SCALE))
        expected_loser = 1 - expected_winner
        new_winner = round(winner_elo + self._k * (WIN - expected_winner))
        new_loser = round(loser_elo + self._k * (LOSS - expected_loser))
        return new_winner, new_loser
