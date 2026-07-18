from kfchess.model.piece import Color


class ScorePrinter:
    """Prints the running capture-point score, one line: 'White: <w>  Black: <b>'."""

    def print(self, scores: dict) -> None:
        white = scores.get(Color.WHITE.value, 0)
        black = scores.get(Color.BLACK.value, 0)
        print(f"White: {white}  Black: {black}")
