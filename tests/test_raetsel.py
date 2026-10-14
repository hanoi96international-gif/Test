import random

from raetselfabrik import labyrinth, sudoku, wortsuche
from raetselfabrik.__main__ import build


def test_sudoku_eindeutig_und_korrekt():
    rng = random.Random(1)
    for diff in sudoku.DIFFICULTY_CLUES:
        puzzle, solution = sudoku.generate(rng, diff)
        assert sudoku.is_valid_solution(solution)
        assert all(p in (0, s) for p, s in zip(puzzle, solution))
        assert sudoku._count_solutions(puzzle[:]) == 1


def test_wortsuche_woerter_stehen_im_gitter():
    grid, words, positions = wortsuche.generate(random.Random(2), "Tiere", difficulty="schwer")
    assert len(words) == 12
    for word, cells in zip(words, positions):
        assert "".join(grid[r][c] for r, c in cells) == word


def test_labyrinth_hat_durchgehenden_weg():
    walls, path = labyrinth.generate(random.Random(3), 12, 15)
    assert path[0] == (0, 0) and path[-1] == (14, 11)
    assert len(walls) == 12 * 15


def test_heft_wird_erzeugt(tmp_path):
    pdf, listing = build(2026, 42, "letter", tmp_path, per_type=3)
    assert pdf.read_bytes().startswith(b"%PDF")
    assert "Sudokus" in listing.read_text(encoding="utf-8")
