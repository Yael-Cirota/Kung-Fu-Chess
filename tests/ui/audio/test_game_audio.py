from kfchess.api import BoardSnapshot, PieceView, Position

from ui.audio.game_audio import GameAudioTracker


class FakeSoundBoard:
    def __init__(self):
        self.played = []

    def play(self, name):
        self.played.append(name)


def piece(piece_id, row=0, col=0):
    return PieceView(piece_id=piece_id, symbol="wP", color="w", cell=Position(row, col))


def snapshot(*pieces):
    return BoardSnapshot(rows=8, cols=8, piece_views=list(pieces))


def no_motion(piece_id):
    return None


class TestGameAudioTracker:
    def test_first_frame_establishes_a_baseline_without_playing_anything(self):
        sound_board = FakeSoundBoard()
        tracker = GameAudioTracker(sound_board)

        tracker.update(snapshot(piece(1), piece(2)), no_motion)

        assert sound_board.played == []

    def test_a_quiet_frame_with_no_changes_plays_nothing(self):
        sound_board = FakeSoundBoard()
        tracker = GameAudioTracker(sound_board)
        board = snapshot(piece(1), piece(2))

        tracker.update(board, no_motion)
        tracker.update(board, no_motion)

        assert sound_board.played == []

    def test_a_piece_newly_in_motion_plays_move(self):
        sound_board = FakeSoundBoard()
        tracker = GameAudioTracker(sound_board)
        board = snapshot(piece(1), piece(2))

        def moving(piece_id):
            return "some-motion" if piece_id == 1 else None

        tracker.update(board, no_motion)
        tracker.update(board, moving)

        assert sound_board.played == ["move"]

    def test_a_piece_already_in_motion_does_not_replay_move(self):
        sound_board = FakeSoundBoard()
        tracker = GameAudioTracker(sound_board)
        board = snapshot(piece(1), piece(2))

        def moving(piece_id):
            return "some-motion" if piece_id == 1 else None

        tracker.update(board, moving)
        tracker.update(board, moving)

        assert sound_board.played == []

    def test_a_dropped_piece_count_plays_capture(self):
        sound_board = FakeSoundBoard()
        tracker = GameAudioTracker(sound_board)

        tracker.update(snapshot(piece(1), piece(2)), no_motion)
        tracker.update(snapshot(piece(1)), no_motion)

        assert sound_board.played == ["capture"]

    def test_capture_and_a_newly_moving_piece_in_the_same_frame_play_both(self):
        sound_board = FakeSoundBoard()
        tracker = GameAudioTracker(sound_board)

        def moving(piece_id):
            return "some-motion" if piece_id == 1 else None

        tracker.update(snapshot(piece(1), piece(2), piece(3)), no_motion)
        tracker.update(snapshot(piece(1), piece(2)), moving)

        assert sound_board.played == ["capture", "move"]
