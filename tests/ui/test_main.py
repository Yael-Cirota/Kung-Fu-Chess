import ui.main as main_module
from ui.main import cell_center_px, main
from ui.ui_config import CELL_SIZE_PX


class TestCellCenterPx:
    def test_center_of_top_left_cell(self):
        assert cell_center_px(0, 0) == (CELL_SIZE_PX // 2, CELL_SIZE_PX // 2)

    def test_center_accounts_for_row_and_col(self):
        x, y = cell_center_px(2, 3)
        assert x == 3 * CELL_SIZE_PX + CELL_SIZE_PX // 2
        assert y == 2 * CELL_SIZE_PX + CELL_SIZE_PX // 2


class FakeWindowCv2:
    """Stands in for cv2 inside ui.graphics.img_canvas so main(show_window=True) never touches a real display."""

    def __init__(self):
        self.destroy_window_calls = []

    def imshow(self, title, array):
        pass

    def waitKey(self, delay_ms):
        return ord("a")  # never the quit key

    def imwrite(self, path, array):
        import cv2  # real cv2, so the demo's output files still land on disk
        return cv2.imwrite(path, array)

    def destroyWindow(self, title):
        self.destroy_window_calls.append(title)


class TestMain:
    def test_runs_full_demo_without_a_window_and_writes_output_files(self, tmp_path, monkeypatch):
        frames_dir = tmp_path / "frames"
        board_path = tmp_path / "rendered_board.png"
        monkeypatch.setattr(main_module, "ANIMATION_FRAMES_OUTPUT_DIR", frames_dir)
        monkeypatch.setattr(main_module, "RENDERED_BOARD_OUTPUT_PATH", board_path)

        main(show_window=False)

        assert board_path.exists()
        assert frames_dir.exists()
        assert len(list(frames_dir.glob("*.png"))) > 0

    def test_runs_with_a_window_and_closes_it_when_done(self, tmp_path, monkeypatch):
        import ui.graphics.img_canvas as img_canvas_module

        frames_dir = tmp_path / "frames"
        board_path = tmp_path / "rendered_board.png"
        monkeypatch.setattr(main_module, "ANIMATION_FRAMES_OUTPUT_DIR", frames_dir)
        monkeypatch.setattr(main_module, "RENDERED_BOARD_OUTPUT_PATH", board_path)
        fake_cv2 = FakeWindowCv2()
        monkeypatch.setattr(img_canvas_module, "cv2", fake_cv2)

        main(show_window=True)

        assert board_path.exists()
        assert fake_cv2.destroy_window_calls == ["Kung-Fu-Chess - Stage 4 motion demo"]
