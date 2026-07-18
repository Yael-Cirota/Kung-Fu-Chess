from kfchess.io.score_printer import ScorePrinter


def test_print_prints_both_totals_on_one_line(capsys):
    ScorePrinter().print({"w": 7, "b": 3})

    assert capsys.readouterr().out == "White: 7  Black: 3\n"


def test_missing_colors_default_to_zero(capsys):
    ScorePrinter().print({})

    assert capsys.readouterr().out == "White: 0  Black: 0\n"
