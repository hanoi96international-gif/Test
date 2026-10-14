"""Setzt die Rätsel als druckfertiges PDF-Buch (A4 oder US-Letter für Amazon KDP)."""

from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import A4, letter
from reportlab.pdfgen import canvas as pdfcanvas

PAGE_SIZES = {"a4": A4, "letter": letter}
ACCENT = HexColor("#d9480f")
SOFT = HexColor("#ffe8cc")
MARGIN = 54


def draw_sudoku(c, x, y, size, grid, solution=None):
    cell = size / 9
    for i, val in enumerate(solution or grid):
        r, col = divmod(i, 9)
        if val:
            given = grid[i] != 0
            c.setFillColor(black if given else ACCENT)
            c.setFont("Helvetica-Bold" if given else "Helvetica", cell * 0.6)
            c.drawCentredString(x + (col + 0.5) * cell, y + size - (r + 0.5) * cell - cell * 0.2, str(val))
    c.setStrokeColor(black)
    for i in range(10):
        c.setLineWidth(2 if i % 3 == 0 else 0.5)
        c.line(x + i * cell, y, x + i * cell, y + size)
        c.line(x, y + i * cell, x + size, y + i * cell)


def draw_wortsuche(c, x, y, size, grid, positions=None):
    n = len(grid)
    cell = size / n
    if positions:
        c.setStrokeColor(ACCENT)
        c.setLineWidth(cell * 0.55)
        c.setLineCap(1)
        c.setStrokeAlpha(0.35)
        for cells in positions:
            (r1, c1), (r2, c2) = cells[0], cells[-1]
            c.line(x + (c1 + 0.5) * cell, y + size - (r1 + 0.5) * cell,
                   x + (c2 + 0.5) * cell, y + size - (r2 + 0.5) * cell)
        c.setStrokeAlpha(1)
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", cell * 0.55)
    for r, row in enumerate(grid):
        for col, ch in enumerate(row):
            c.drawCentredString(x + (col + 0.5) * cell, y + size - (r + 0.5) * cell - cell * 0.2, ch)
    c.setStrokeColor(black)
    c.setLineWidth(1.5)
    c.rect(x, y, size, size)


def draw_labyrinth(c, x, y, box_w, box_h, walls, path=None):
    rows = max(r for r, _ in walls) + 1
    cols = max(col for _, col in walls) + 1
    cell = min(box_w / cols, box_h / rows)
    ox = x + (box_w - cell * cols) / 2
    top = y + box_h - (box_h - cell * rows) / 2

    def pt(r, col):
        return ox + col * cell, top - r * cell

    if path:
        c.setStrokeColor(ACCENT)
        c.setLineWidth(max(cell * 0.22, 0.8))
        p = c.beginPath()
        for i, (r, col) in enumerate(path):
            px, py = ox + (col + 0.5) * cell, top - (r + 0.5) * cell
            p.moveTo(px, py) if i == 0 else p.lineTo(px, py)
        c.drawPath(p, stroke=1, fill=0)
    c.setStrokeColor(black)
    c.setLineWidth(max(cell * 0.08, 0.6))
    c.setLineCap(2)
    for (r, col), sides in walls.items():
        x0, y0 = pt(r, col)
        x1, y1 = pt(r + 1, col + 1)
        if "N" in sides:
            c.line(x0, y0, x1, y0)
        if "S" in sides:
            c.line(x0, y1, x1, y1)
        if "W" in sides:
            c.line(x0, y0, x0, y1)
        if "O" in sides:
            c.line(x1, y0, x1, y1)


class Book:
    def __init__(self, path, title, subtitle, page_format="a4"):
        self.size = PAGE_SIZES[page_format]
        self.c = pdfcanvas.Canvas(path, pagesize=self.size)
        self.c.setTitle(title)
        self.c.setAuthor("Rätselfabrik")
        self.title, self.subtitle = title, subtitle
        self.page_no = 0

    @property
    def w(self):
        return self.size[0]

    @property
    def h(self):
        return self.size[1]

    def _finish_page(self, numbered=True):
        if numbered:
            self.c.setFont("Helvetica", 9)
            self.c.setFillColor(black)
            self.c.drawCentredString(self.w / 2, MARGIN / 2, str(self.page_no))
        self.c.showPage()
        self.page_no += 1

    def cover(self, theme, contents):
        c = self.c
        c.setFillColor(SOFT)
        c.rect(0, 0, self.w, self.h, fill=1, stroke=0)
        c.setFillColor(ACCENT)
        c.rect(0, self.h * 0.62, self.w, self.h * 0.2, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 40)
        c.drawCentredString(self.w / 2, self.h * 0.73, "RÄTSELFABRIK")
        c.setFont("Helvetica", 18)
        c.drawCentredString(self.w / 2, self.h * 0.66, self.subtitle)
        c.setFillColor(black)
        c.setFont("Helvetica-Bold", 26)
        c.drawCentredString(self.w / 2, self.h * 0.5, f"Thema: {theme}")
        c.setFont("Helvetica", 15)
        for i, line in enumerate(contents):
            c.drawCentredString(self.w / 2, self.h * 0.42 - i * 24, line)
        c.setFont("Helvetica-Oblique", 12)
        c.drawCentredString(self.w / 2, self.h * 0.12, "Mit allen Lösungen am Ende des Heftes")
        self._finish_page(numbered=False)

    def heading(self, text):
        self.c.setFillColor(ACCENT)
        self.c.setFont("Helvetica-Bold", 22)
        self.c.drawString(MARGIN, self.h - MARGIN - 10, text)
        self.c.setFillColor(black)

    def intro(self):
        self.heading("So funktioniert's")
        lines = [
            "SUDOKU: Fülle jedes Feld mit einer Zahl von 1 bis 9. Jede Zeile, jede Spalte",
            "und jedes 3x3-Kästchen enthält jede Zahl genau einmal.",
            "",
            "WORTSUCHE: Finde alle Wörter aus der Liste im Buchstabengitter. Sie können",
            "waagerecht, senkrecht, diagonal und je nach Schwierigkeit auch rückwärts stehen.",
            "",
            "LABYRINTH: Finde den Weg vom Eingang oben links zum Ausgang unten rechts.",
            "",
            "Viel Spaß beim Rätseln!",
        ]
        self.c.setFont("Helvetica", 12)
        for i, line in enumerate(lines):
            self.c.drawString(MARGIN, self.h - MARGIN - 60 - i * 18, line)
        self._finish_page()

    def full_page(self, heading, draw, footer_lines=()):
        self.heading(heading)
        avail_w = self.w - 2 * MARGIN
        avail_h = self.h - 2 * MARGIN - 60 - len(footer_lines) * 16
        draw(MARGIN, MARGIN + 20 + len(footer_lines) * 16, avail_w, avail_h)
        self.c.setFont("Helvetica", 12)
        for i, line in enumerate(footer_lines):
            self.c.drawString(MARGIN, MARGIN + 10 + (len(footer_lines) - 1 - i) * 16, line)
        self._finish_page()

    def solution_pages(self, items):
        """items: Liste von (überschrift, draw(x, y, w, h)); vier Lösungen pro Seite."""
        cell_w = (self.w - 2 * MARGIN - 20) / 2
        cell_h = (self.h - 2 * MARGIN - 80) / 2
        for start in range(0, len(items), 4):
            self.heading("Lösungen")
            for k, (label, draw) in enumerate(items[start:start + 4]):
                col, row = k % 2, k // 2
                x = MARGIN + col * (cell_w + 20)
                y = self.h - MARGIN - 50 - (row + 1) * cell_h
                self.c.setFont("Helvetica-Bold", 11)
                self.c.drawString(x, y + cell_h - 14, label)
                draw(x, y, cell_w, cell_h - 24)
            self._finish_page()

    def save(self):
        self.c.save()
