"""Labyrinth-Generator (Recursive Backtracker) mit Lösungsweg."""

import random
from collections import deque


def generate(rng: random.Random, width: int = 20, height: int = 25):
    """Gibt (wände, lösung) zurück.

    wände[(r, c)] ist eine Menge der noch geschlossenen Seiten aus {"N", "S", "W", "O"}.
    Eingang oben links (Norden), Ausgang unten rechts (Süden).
    """
    walls = {(r, c): {"N", "S", "W", "O"} for r in range(height) for c in range(width)}
    moves = {"N": (-1, 0, "S"), "S": (1, 0, "N"), "W": (0, -1, "O"), "O": (0, 1, "W")}
    stack, seen = [(0, 0)], {(0, 0)}
    while stack:
        r, c = stack[-1]
        options = [(d, r + dr, c + dc, back) for d, (dr, dc, back) in moves.items()
                   if (r + dr, c + dc) in walls and (r + dr, c + dc) not in seen]
        if not options:
            stack.pop()
            continue
        d, nr, nc, back = rng.choice(options)
        walls[(r, c)].discard(d)
        walls[(nr, nc)].discard(back)
        seen.add((nr, nc))
        stack.append((nr, nc))
    walls[(0, 0)].discard("N")
    walls[(height - 1, width - 1)].discard("S")
    return walls, solve(walls, moves, width, height)


def solve(walls, moves, width, height):
    start, goal = (0, 0), (height - 1, width - 1)
    prev, queue = {start: None}, deque([start])
    while queue:
        cell = queue.popleft()
        if cell == goal:
            break
        for d, (dr, dc, _) in moves.items():
            nxt = (cell[0] + dr, cell[1] + dc)
            if d not in walls[cell] and nxt in walls and nxt not in prev:
                prev[nxt] = cell
                queue.append(nxt)
    path, cell = [], goal
    while cell is not None:
        path.append(cell)
        cell = prev[cell]
    return path[::-1]
