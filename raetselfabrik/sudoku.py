"""Sudoku-Generator mit garantiert eindeutiger Lösung."""

import random

DIFFICULTY_CLUES = {"leicht": 40, "mittel": 32, "schwer": 26}


def _candidates(grid, idx):
    r, c = divmod(idx, 9)
    used = set(grid[r * 9:(r + 1) * 9]) | {grid[i * 9 + c] for i in range(9)}
    br, bc = r // 3 * 3, c // 3 * 3
    used |= {grid[(br + i) * 9 + bc + j] for i in range(3) for j in range(3)}
    return [n for n in range(1, 10) if n not in used]


def _count_solutions(grid, limit=2):
    empties = [i for i, v in enumerate(grid) if v == 0]
    if not empties:
        return 1
    # Feld mit den wenigsten Kandidaten zuerst
    best, best_cands = None, None
    for i in empties:
        cands = _candidates(grid, i)
        if best_cands is None or len(cands) < len(best_cands):
            best, best_cands = i, cands
            if len(cands) <= 1:
                break
    count = 0
    for n in best_cands:
        grid[best] = n
        count += _count_solutions(grid, limit - count)
        grid[best] = 0
        if count >= limit:
            break
    return count


def _fill(grid, rng):
    try:
        idx = grid.index(0)
    except ValueError:
        return True
    cands = _candidates(grid, idx)
    rng.shuffle(cands)
    for n in cands:
        grid[idx] = n
        if _fill(grid, rng):
            return True
    grid[idx] = 0
    return False


def generate(rng: random.Random, difficulty: str = "mittel"):
    """Gibt (rätsel, lösung) als Listen mit 81 Zahlen zurück; 0 = leeres Feld."""
    solution = [0] * 81
    _fill(solution, rng)
    puzzle = solution[:]
    target = DIFFICULTY_CLUES[difficulty]
    cells = list(range(81))
    rng.shuffle(cells)
    for idx in cells:
        if sum(1 for v in puzzle if v) <= target:
            break
        backup = puzzle[idx]
        puzzle[idx] = 0
        if _count_solutions(puzzle[:]) != 1:
            puzzle[idx] = backup
    return puzzle, solution


def is_valid_solution(grid):
    groups = []
    for i in range(9):
        groups.append(grid[i * 9:(i + 1) * 9])
        groups.append([grid[r * 9 + i] for r in range(9)])
        br, bc = i // 3 * 3, i % 3 * 3
        groups.append([grid[(br + a) * 9 + bc + b] for a in range(3) for b in range(3)])
    return all(sorted(g) == list(range(1, 10)) for g in groups)
