from pathlib import Path


class SpriteResolver:
    """
    Translates a piece symbol ('wK', 'bP', ...) into the sprite file for
    it inside a skin folder. The skin's on-disk naming convention -
    <kind><COLOR>/states/<state>/sprites/<frame filename> - is
    encapsulated here alone, so a different skin (different folder
    layout, different filenames) only ever requires constructing this
    class with different arguments - SpriteLoader and BoardRenderer
    never need to change.
    """

    def __init__(self, pieces_dir: Path, state: str, frame_filename: str):
        self._pieces_dir = Path(pieces_dir)
        self._state = state
        self._frame_filename = frame_filename

    def resolve(self, piece_symbol: str, state: str = None, frame_index: int = None) -> Path:
        """
        Defaults to the configured static (state, frame) pair when called
        with just a symbol (Stage 2/3 behavior, unchanged). Pass state and
        frame_index to resolve a specific animation frame instead - frame
        filenames are 1-indexed on disk (1.png, 2.png, ...).
        """
        color_letter, kind_letter = piece_symbol[0], piece_symbol[1]
        piece_folder = f"{kind_letter.upper()}{color_letter.upper()}"
        state = state if state is not None else self._state
        frame_filename = f"{frame_index + 1}.png" if frame_index is not None else self._frame_filename
        return self._pieces_dir / piece_folder / "states" / state / "sprites" / frame_filename
