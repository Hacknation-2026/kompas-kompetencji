"""Generate a 10-slide 16:9 widescreen PDF presentation for HackNation 2026 jury."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

from fpdf import FPDF

# 16:9 widescreen (standard 13.333 x 7.5 in = 338.67 x 190.5 mm)
W = 338.67
H = 190.50

# Brand palette (Ministerstwo Cyfryzacji / Kompas Kompetencji)
NAVY = (11, 37, 69)
NAVY_DARK = (7, 25, 48)
NAVY_MID = (18, 54, 99)
BLUE = (29, 95, 167)
BLUE_LIGHT = (232, 241, 251)
BLUE_BORDER = (191, 215, 242)
PURPLE = (96, 57, 158)
PURPLE_LIGHT = (242, 236, 250)
PURPLE_BORDER = (215, 196, 240)
CRIMSON = (212, 33, 61)
BG = (244, 246, 249)
WHITE = (255, 255, 255)
BORDER = (217, 226, 236)
TEXT = (16, 42, 67)
MUTED = (72, 101, 129)
OK_BG = (230, 244, 234)
OK_FG = (14, 96, 39)
OK_BORDER = (183, 223, 193)
WARN_BG = (255, 248, 225)
WARN_FG = (138, 83, 0)
ERR_BG = (253, 236, 234)
ERR_FG = (162, 25, 31)
SKY = (142, 197, 255)


class DeckPDF(FPDF):
    def __init__(self) -> None:
        super().__init__(orientation="L", unit="mm", format=(H, W))
        self.set_auto_page_break(False)
        self.set_margins(0, 0, 0)
        fonts = Path("C:/Windows/Fonts")
        self.add_font("UI", "", str(fonts / "segoeui.ttf"))
        self.add_font("UI", "B", str(fonts / "segoeuib.ttf"))
        self.add_font("UI", "I", str(fonts / "segoeuii.ttf"))
        self.add_font("Mono", "", str(fonts / "consola.ttf"))
        self.add_font("Mono", "B", str(fonts / "consolab.ttf"))

    # --- Primitives ---------------------------------------------------------
    def rect_fill(self, x: float, y: float, w: float, h: float, color: tuple[int, int, int]) -> None:
        self.set_fill_color(*color)
        self.rect(x, y, w, h, style="F")

    def card(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        *,
        fill: tuple[int, int, int] = WHITE,
        border: tuple[int, int, int] | None = BORDER,
        radius: float = 3.5,
        top_bar: tuple[int, int, int] | None = None,
        left_bar: tuple[int, int, int] | None = None,
    ) -> None:
        self.set_fill_color(*fill)
        if border is not None:
            self.set_draw_color(*border)
            self.set_line_width(0.35)
            style = "DF"
        else:
            style = "F"
        self.rect(x, y, w, h, style=style, round_corners=True, corner_radius=radius)
        if top_bar is not None:
            self.set_fill_color(*top_bar)
            self.rect(x, y, w, 1.8, style="F")
        if left_bar is not None:
            self.set_fill_color(*left_bar)
            self.rect(x, y, 2.0, h, style="F")

    def pill(
        self,
        x: float,
        y: float,
        text: str,
        *,
        bg: tuple[int, int, int] = BLUE_LIGHT,
        fg: tuple[int, int, int] = NAVY,
        font_size: float = 8.5,
        pad_x: float = 4.2,
        height: float = 6.6,
        align_right: bool = False,
    ) -> float:
        self.set_font("UI", "B", font_size)
        tw = self.get_string_width(text)
        pw = tw + pad_x * 2
        px = x - pw if align_right else x
        self.set_fill_color(*bg)
        self.rect(px, y, pw, height, style="F", round_corners=True, corner_radius=height / 2)
        self.set_text_color(*fg)
        self.set_xy(px, y + 1.0)
        self.cell(pw, height - 2.0, text, align="C")
        return pw

    def txt(
        self,
        x: float,
        y: float,
        w: float,
        text: str,
        *,
        size: float = 10.5,
        style: str = "",
        color: tuple[int, int, int] = TEXT,
        line_h: float = 5.0,
        align: str = "L",
        font: str = "UI",
    ) -> float:
        self.set_font(font, style, size)
        self.set_text_color(*color)
        self.set_xy(x, y)
        self.multi_cell(w, line_h, text, align=align)
        return self.get_y()

    def bullets(
        self,
        x: float,
        y: float,
        w: float,
        items: Iterable[tuple[str, str]],
        *,
        size: float = 10.0,
        line_h: float = 4.9,
        gap: float = 2.6,
        text_color: tuple[int, int, int] = TEXT,
        bullet_color: tuple[int, int, int] = BLUE,
    ) -> float:
        cy = y
        for lead, body in items:
            self.set_fill_color(*bullet_color)
            self.ellipse(x + 0.6, cy + 1.65, 1.8, 1.8, style="F")
            self.set_font("UI", "", size)
            self.set_xy(x + 4.5, cy)
            self.set_text_color(*text_color)
            full = f"**{lead}** {body}" if lead else body
            self.multi_cell(w - 4.5, line_h, full, markdown=True)
            cy = self.get_y() + gap
        return cy

    # --- Slide chrome -------------------------------------------------------
    def start_content_slide(
        self,
        slide_no: int,
        kicker: str,
        title: str,
        badge: str,
        badge_bg: tuple[int, int, int] = NAVY,
    ) -> None:
        self.add_page()
        self.rect_fill(0, 0, W, H, BG)
        # Top accent stripe
        self.rect_fill(0, 0, W * 0.65, 2.0, NAVY)
        self.rect_fill(W * 0.65, 0, W * 0.25, 2.0, BLUE)
        self.rect_fill(W * 0.90, 0, W * 0.10, 2.0, CRIMSON)

        # Header
        self.txt(16, 10, 220, kicker.upper(), size=8.5, style="B", color=BLUE, line_h=4.0)
        self.txt(16, 15.2, 240, title, size=20.5, style="B", color=NAVY, line_h=8.5)
        self.pill(W - 16, 14, badge, bg=badge_bg, fg=WHITE, font_size=8.8, height=7.2, align_right=True)

        # Footer
        self.set_draw_color(*BORDER)
        self.set_line_width(0.3)
        self.line(16, H - 11.5, W - 16, H - 11.5)
        self.txt(16, H - 9.2, 200, "Kompas Kompetencji  ·  HackNation 2026 — Ministerstwo Cyfryzacji (BDG)", size=8.2, color=MUTED, line_h=4.0)
        self.txt(W - 46, H - 9.2, 30, f"Slajd {slide_no} / 10", size=8.2, style="B", color=MUTED, line_h=4.0, align="R")

    def banner(self, y: float, lead: str, body: str, pill_text: str | None = None) -> None:
        self.card(16, y, W - 32, 14.5, fill=NAVY, border=None, radius=3.0)
        text_w = W - 96 if pill_text else W - 44
        self.set_font("UI", "", 9.4)
        self.set_text_color(232, 240, 250)
        self.set_xy(21, y + 3.0)
        self.multi_cell(text_w, 4.4, f"**{lead}** {body}", markdown=True)
        if pill_text:
            self.pill(W - 21, y + 4.0, pill_text, bg=NAVY_MID, fg=SKY, font_size=8.3, height=6.6, align_right=True)

    # --- Compass emblem (Slide 1) -------------------------------------------
    def draw_compass(self, cx: float, cy: float, r: float) -> None:
        # Outer rings
        self.set_draw_color(60, 110, 170)
        self.set_line_width(0.5)
        self.ellipse(cx - r, cy - r, r * 2, r * 2, style="D")
        r2 = r * 0.80
        self.set_fill_color(17, 50, 92)
        self.set_draw_color(*SKY)
        self.set_line_width(0.8)
        self.ellipse(cx - r2, cy - r2, r2 * 2, r2 * 2, style="DF")
        r3 = r * 0.56
        self.set_draw_color(60, 110, 170)
        self.set_line_width(0.4)
        self.ellipse(cx - r3, cy - r3, r3 * 2, r3 * 2, style="D")

        # Cardinal ticks
        self.set_draw_color(*WHITE)
        self.set_line_width(0.9)
        for angle_deg in (0, 90, 180, 270):
            rad = math.radians(angle_deg)
            x1 = cx + math.cos(rad) * (r2 - 1.5)
            y1 = cy + math.sin(rad) * (r2 - 1.5)
            x2 = cx + math.cos(rad) * (r2 - 7.0)
            y2 = cy + math.sin(rad) * (r2 - 7.0)
            self.line(x1, y1, x2, y2)

        # Needle north (crimson) and south (white)
        self.set_fill_color(*CRIMSON)
        self.polygon([(cx, cy - r2 * 0.78), (cx + 6.5, cy), (cx, cy - 4.5), (cx - 6.5, cy)], style="F")
        self.set_fill_color(*WHITE)
        self.polygon([(cx, cy + r2 * 0.78), (cx + 6.5, cy), (cx, cy + 4.5), (cx - 6.5, cy)], style="F")

        # Center hub
        self.set_fill_color(*NAVY_DARK)
        self.set_draw_color(*SKY)
        self.set_line_width(1.1)
        self.ellipse(cx - 4.2, cy - 4.2, 8.4, 8.4, style="DF")

        # Labels
        self.txt(cx - 14, cy - r - 6.5, 28, "PRAWO", size=8.2, style="B", color=SKY, align="C")
        self.txt(cx - 14, cy + r + 2.0, 28, "ROZWÓJ", size=8.2, style="B", color=SKY, align="C")
        self.txt(cx - r - 16, cy - 2.3, 14, "AI", size=8.2, style="B", color=SKY, align="R")
        self.txt(cx + r + 2, cy - 2.3, 14, "HR", size=8.2, style="B", color=SKY, align="L")


def build_pdf(output_path: Path) -> None:
    pdf = DeckPDF()

    # ========================================================================
    # SLAJD 1: TYTUŁOWY
    # ========================================================================
    pdf.add_page()
    pdf.rect_fill(0, 0, W, H, NAVY_DARK)
    # Subtle lighter right accent panel
    pdf.set_fill_color(*NAVY)
    pdf.polygon([(W * 0.58, 0), (W, 0), (W, H), (W * 0.48, H)], style="F")
    # Polish white-red top stripe
    pdf.rect_fill(0, 0, W / 2, 2.5, WHITE)
    pdf.rect_fill(W / 2, 0, W / 2, 2.5, CRIMSON)

    pdf.pill(20, 14, "HACKNATION 2026  ·  MINISTERSTWO CYFRYZACJI — BDG", bg=NAVY_MID, fg=WHITE, font_size=8.8, height=7.2)
    pdf.pill(W - 20, 14, "PROTOTYP + GOTOWOŚĆ PRODUKCYJNA", bg=NAVY_MID, fg=SKY, font_size=8.8, height=7.2, align_right=True)

    pdf.txt(20, 44, 190, "SYSTEM WSPARCIA OCEN PRACOWNICZYCH W SŁUŻBIE CYWILNEJ", size=10, style="B", color=SKY, line_h=5)
    pdf.txt(20, 52, 195, "Kompas Kompetencji", size=38, style="B", color=WHITE, line_h=15)
    pdf.set_font("UI", "", 13.5)
    pdf.set_text_color(215, 228, 242)
    pdf.set_xy(20, 76)
    pdf.multi_cell(
        186,
        6.6,
        "Jedno spójne narzędzie prowadzące przełożonego krok po kroku przez **proces formalny**, "
        "**model kompetencyjny** i **rozmowę oceniającą** — z lokalnym asystentem AI (Bielik + RAG), "
        "który doradza, ale **nigdy nie zastępuje decyzji człowieka**.",
        markdown=True,
    )

    # Feature pills (2x2)
    pills_s1 = [
        ("• Pierwsza ocena (2015) & Okresowa (2016)", 20, 118),
        ("• 14 kompetencji · 49 wskaźników", 107, 118),
        ("• Lokalny Bielik 11B (Apache 2.0)", 20, 129),
        ("• Eksport PDF + Panel HR", 107, 129),
    ]
    for label, px, py in pills_s1:
        pdf.pill(px, py, label, bg=(24, 62, 108), fg=WHITE, font_size=9.0, height=7.8)

    pdf.draw_compass(268, 95, 36)

    pdf.set_draw_color(42, 74, 115)
    pdf.line(20, H - 14, W - 20, H - 14)
    pdf.txt(20, H - 10.5, 220, "Kompas Kompetencji — Wyzwanie: Ministerstwo Cyfryzacji (Biuro Dyrektora Generalnego)", size=8.5, color=(180, 200, 222))
    pdf.txt(W - 50, H - 10.5, 30, "Slajd 1 / 10", size=8.5, style="B", color=(180, 200, 222), align="R")

    # ========================================================================
    # SLAJD 2: PROBLEM
    # ========================================================================
    pdf.start_content_slide(
        2,
        "01 · Kontekst i wyzwanie",
        "Dlaczego ocenianie w służbie cywilnej wymaga wsparcia?",
        "Merytoryka · 25%",
        NAVY,
    )

    # Left 3 stacked cards
    left_w = 176
    problems = [
        (
            "Ryzyko formalne",
            ERR_BG,
            ERR_FG,
            "Rozproszone przepisy i rygorystyczne terminy",
            "Przełożony musi jednocześnie stosować ustawę o służbie cywilnej, 2 rozporządzenia (2015 i 2016), "
            "poradniki KPRM oraz reguły terminów z Kodeksu cywilnego (art. 111–115). Błąd w wyborze arkusza (A/B/C) "
            "lub terminie (21 / 30 dni, przedłużenia) grozi sprzeciwem pracownika.",
        ),
        (
            "Subiektywność",
            WARN_BG,
            WARN_FG,
            "Trudność przełożenia zachowań na skalę ocen",
            "Pojęcia takie jak Komunikacja czy Myślenie analityczne są szerokie. Bez powiązania oceny z konkretnymi "
            "wskaźnikami behawioralnymi (49) i faktami (STAR), oceny stają się niespójne między przełożonymi i departamentami.",
        ),
        (
            "Rozmowa i HR",
            PURPLE_LIGHT,
            PURPLE,
            "Brak wsparcia w rozmowie i bieżącym monitoringu",
            "Ocena powinna budować wartościowy feedback i Indywidualny Program Rozwoju Zawodowego (IPRZ), a kadry (HR) "
            "potrzebują jednego widoku terminów, statusów i przypomnień zamiast ręcznych arkuszy.",
        ),
    ]
    cy = 31
    for tag, tbg, tfg, heading, body in problems:
        pdf.card(16, cy, left_w, 43.5)
        pw = pdf.pill(22, cy + 5.0, tag, bg=tbg, fg=tfg, font_size=8.2, height=6.2)
        pdf.txt(22 + pw + 3.5, cy + 5.2, left_w - pw - 16, heading, size=11.5, style="B", color=NAVY, line_h=5.2)
        pdf.txt(22, cy + 14.5, left_w - 12, body, size=9.6, color=MUTED, line_h=4.6)
        cy += 47.5

    # Right Navy solution card
    rx = 16 + left_w + 8
    rw = W - rx - 16
    pdf.card(rx, 31, rw, 138.5, fill=NAVY, border=None)
    pdf.pill(rx + 7, 38, "NASZA ODPOWIEDŹ", bg=NAVY_MID, fg=SKY, font_size=8.2, height=6.4)
    pdf.txt(rx + 7, 48, rw - 14, "Jedno narzędzie zamiast\n5 PDF-ów i rozproszonych plików", size=15.5, style="B", color=WHITE, line_h=6.8)
    pdf.bullets(
        rx + 7,
        66,
        rw - 14,
        [
            ("Prowadzenie krok po kroku", "z walidacją przepisów przed każdym kolejnym etapem."),
            ("Automatyczny dobór arkusza A/B/C", "na podstawie wgranego pliku OSP (.docx / .pdf)."),
            ("Ocena oparta na zachowaniach", "z pomocniczą sugestią poziomu i wyłączną decyzją przełożonego."),
            ("Lokalny Asystent AI (Bielik)", "odpowiadający z cytowaniami źródeł oraz przygotowujący rozmowę."),
            ("Panel HR i eksport PDF", "eliminujące ręczną biurokrację i pilnowanie terminów."),
        ],
        size=9.8,
        line_h=4.8,
        gap=3.5,
        text_color=(230, 239, 249),
        bullet_color=SKY,
    )
    pdf.card(rx + 7, 148, rw - 14, 15.5, fill=NAVY_MID, border=None, radius=2.5)
    pdf.txt(rx + 11, 151.0, rw - 22, "Cel: spójna, obiektywna, zgodna z prawem ocena — przy pełnej odpowiedzialności przełożonego.", size=9.2, style="B", color=(215, 232, 255), line_h=4.4)

    # ========================================================================
    # SLAJD 3: ROZWIĄZANIE — DWIE KOMPLETNE ŚCIEŻKI PROCESU
    # ========================================================================
    pdf.start_content_slide(
        3,
        "02 · Logika procesu",
        "Dwie kompletne ścieżki zgodne z rozporządzeniami",
        "Zgodność prawna · 100%",
        NAVY,
    )

    col_w = (W - 32 - 8) / 2
    paths = [
        (
            16,
            "Ścieżka 1: Pierwsza ocena",
            "Rozp. 23.07.2015 · 3 / 5 / 7 pkt",
            BLUE,
            BLUE_LIGHT,
            [
                ("Rozmowa wstępna", "Termin ustawowy 21 dni od nawiązania stosunku pracy (omówienie zadań i kryteriów)."),
                ("Sprawozdanie ocenianego (Zał. nr 3)", "Walidacja okresu ≥ 7 mies., główne zadania, problemy, nowe kompetencje, usprawnienia."),
                ("Ocena 5 elementów kompetencyjnych", "Wskaźniki behawioralne, notatki dowodowe STAR i pomocnicza sugestia poziomu (3 / 5 / 7 pkt)."),
                ("Rozmowa, egzamin i wynik końcowy", "Kontrola zaliczenia egzaminu ze służby przygotowawczej + zapoznanie i eksport PDF."),
            ],
        ),
        (
            16 + col_w + 8,
            "Ścieżka 2: Ocena okresowa",
            "Rozp. 04.04.2016 · A/B/C · 1–9 pkt",
            PURPLE,
            PURPLE_LIGHT,
            [
                ("Analiza OSP (.docx / .pdf)", "Rekomendacja formularza A / B / C (z opcją nadpisania) i dopasowanych kryteriów dodatkowych."),
                ("Ustalenie kryteriów (Część I)", "Maks. 3 dodatkowe; termin 30 dni (lub 7 dni przy ponownej ocenie po 6 mies. — art. 81 ust. 9)."),
                ("Ocena wskaźników i rozmowa oceniająca", "Skala 1–9 pkt, dowody STAR, wsparcie Asystenta rozmowy AI i wnioski do IPRZ."),
                ("Wynik (Cz. II), Stopień (Cz. III) i Pouczenie", "Automatyczny wniosek o kolejny stopień dla urzędnika mianowanego + 7 dni na sprzeciw i PDF."),
            ],
        ),
    ]

    for px, title, pill_lbl, accent, pill_bg, steps in paths:
        pdf.card(px, 31, col_w, 121)
        pdf.txt(px + 6, 36.5, col_w - 60, title, size=13, style="B", color=accent, line_h=5.5)
        pdf.pill(px + col_w - 6, 36.0, pill_lbl, bg=pill_bg, fg=accent, font_size=8.0, height=6.4, align_right=True)
        sy = 47.0
        for idx, (st_title, st_body) in enumerate(steps, start=1):
            pdf.card(px + 6, sy, col_w - 12, 23.0, fill=BG, border=BORDER, radius=2.5)
            # Circle number
            pdf.set_fill_color(*accent)
            pdf.ellipse(px + 10, sy + 7.5, 7.5, 7.5, style="F")
            pdf.txt(px + 10, sy + 9.2, 7.5, str(idx), size=9.0, style="B", color=WHITE, align="C", line_h=4.0)
            pdf.txt(px + 20.5, sy + 3.2, col_w - 29, st_title, size=9.8, style="B", color=NAVY, line_h=4.4)
            pdf.txt(px + 20.5, sy + 8.4, col_w - 29, st_body, size=8.9, color=MUTED, line_h=4.2)
            sy += 25.5

    pdf.banner(
        156.5,
        "Silnik terminów (art. 111–115 KC):",
        "automatyczny kalendarz świąt w Polsce, przesuwanie terminów z weekendów/świąt oraz obsługa przedłużeń przy nieobecnościach (§ 5 rozp. 2015 / art. 81 ust. 8 ustawy).",
        pill_text="Walidacja na każdym kroku",
    )

    # ========================================================================
    # SLAJD 4: UX — PERSPEKTYWA PRZEŁOŻONEGO I HR
    # ========================================================================
    pdf.start_content_slide(
        4,
        "03 · Doświadczenie użytkownika",
        "Intuicyjny kreator dla Przełożonego i monitoring dla HR",
        "UX & UI · 25%",
        BLUE,
    )

    # Left: Supervisor
    pdf.card(16, 31, col_w, 139)
    pdf.txt(22, 36.5, 95, "Perspektywa Przełożonego", size=13, style="B", color=NAVY)
    pdf.pill(16 + col_w - 6, 36.0, "Rola: supervisor", bg=BLUE_LIGHT, fg=NAVY, font_size=8.2, height=6.4, align_right=True)

    # Mini wireframe inside card
    pdf.card(22, 47, col_w - 12, 47, fill=BG, border=BORDER, radius=2.5)
    # Stepper pills
    wx = 25
    for lbl, bgc, fgc in [
        ("1. OSP (OK)", NAVY, WHITE),
        ("2. Kryteria (OK)", BLUE, WHITE),
        ("3. Ocena (aktywny)", PURPLE, WHITE),
        ("4. Rozmowa → PDF", (226, 232, 240), MUTED),
    ]:
        pw = pdf.pill(wx, 50.5, lbl, bg=bgc, fg=fgc, font_size=7.4, pad_x=2.8, height=5.8)
        wx += pw + 2.2
    # Two panes inside wireframe
    pdf.card(25, 59.5, 78, 31, fill=WHITE, border=BORDER, radius=2.0)
    pdf.txt(28, 62.5, 72, "Kreator oceny + dowody STAR", size=8.8, style="B", color=NAVY, line_h=4.0)
    pdf.txt(28, 68.0, 72, "Wskaźniki behawioralne, sugestia systemu i jawny wybór oceny przez przełożonego.", size=8.2, color=MUTED, line_h=4.0)

    pdf.card(106, 59.5, col_w - 99, 31, fill=PURPLE_LIGHT, border=PURPLE_BORDER, radius=2.0)
    pdf.txt(109, 62.5, col_w - 105, "Panel boczny AI", size=8.8, style="B", color=PURPLE, line_h=4.0)
    pdf.txt(109, 68.0, col_w - 105, "Zakładki: Asystent formalny oraz Asystent rozmowy.", size=8.2, color=TEXT, line_h=4.0)

    pdf.bullets(
        22,
        101,
        col_w - 12,
        [
            ("Upload pliku OSP (.docx / .pdf)", "z automatyczną analizą stanowiska i doborem arkusza."),
            ("Okno terminów i przedłużeń", "dostępne z nagłówka kreatora na każdym etapie oceny."),
            ("Eksport dokumentacji", "do gotowego arkusza PDF / HTML jednym kliknięciem."),
            ("Szybkie przełączanie ścieżek", "Pierwsza ocena oraz Ocena okresowa z jednego kokpitu."),
        ],
        size=9.7,
        line_h=4.8,
        gap=3.2,
    )

    # Right top: HR
    rx = 16 + col_w + 8
    pdf.card(rx, 31, col_w, 94)
    pdf.txt(rx + 6, 36.5, 95, "Perspektywa Kadr / Administratora", size=13, style="B", color=NAVY)
    pdf.pill(rx + col_w - 6, 36.0, "Rola: hr / admin", bg=OK_BG, fg=OK_FG, font_size=8.2, height=6.4, align_right=True)
    pdf.bullets(
        rx + 6,
        49,
        col_w - 12,
        [
            ("Dashboard postępów", "podgląd statusów wszystkich ocen w urzędzie w czasie rzeczywistym."),
            ("Alerty terminów", "wyróżnienie zbliżających się i zaległych terminów (rozmowa wstępna, kryteria, ocena)."),
            ("Wysyłka przypomnień", "ręcznie z panelu HR lub automatycznie przez cykliczny worker SMTP TLS."),
            ("Pełna rozliczalność", "historia zmian etapów, terminów i przedłużeń (ślad audytowy)."),
        ],
        size=9.7,
        line_h=4.8,
        gap=3.6,
        bullet_color=OK_FG,
    )

    # Right bottom: Desktop & Tablet compliance
    pdf.card(rx, 131, col_w, 39, fill=BLUE_LIGHT, border=BLUE_BORDER)
    pdf.txt(rx + 7, 136.5, col_w - 42, "Wymóg ergonomii MC: Desktop & Tablet", size=11.0, style="B", color=NAVY, line_h=4.8)
    pdf.txt(
        rx + 7,
        143.8,
        col_w - 44,
        "Interfejs celowo blokuje dostęp na smartfonach (< 768px), gwarantując czytelność formularzy, wskaźników behawioralnych i dokumentacji kadrowej.",
        size=9.3,
        color=TEXT,
        line_h=4.6,
    )
    pdf.txt(rx + col_w - 38, 145.5, 32, "≥ 768px", size=16, style="B", color=NAVY, align="R")

    # ========================================================================
    # SLAJD 5: MODEL KOMPETENCYJNY I POMOCNICZA SUGESTIA
    # ========================================================================
    pdf.start_content_slide(
        5,
        "04 · Obiektywizacja oceny",
        "Model kompetencyjny: od zachowań do świadomej decyzji",
        "Human-in-the-Loop",
        OK_FG,
    )

    # 4 stat boxes
    stat_w = (W - 32 - 18) / 4
    stats = [
        ("14", "Kompetencji z arkusza MC", NAVY),
        ("49", "Wskaźników behawioralnych", BLUE),
        ("STAR", "Dowody (Sytuacja–Działanie–Rezultat)", PURPLE),
        ("100%", "Decyzja po stronie przełożonego", OK_FG),
    ]
    for i, (num, lbl, col) in enumerate(stats):
        sx = 16 + i * (stat_w + 6)
        pdf.card(sx, 31, stat_w, 26)
        pdf.txt(sx, 35.5, stat_w, num, size=22, style="B", color=col, align="C", line_h=9.0)
        pdf.txt(sx + 3, 47.0, stat_w - 6, lbl, size=8.8, style="B", color=MUTED, align="C", line_h=4.0)

    # Main flow card
    pdf.card(16, 63, W - 32, 108)
    pdf.txt(23, 69, 250, "Jak działa mechanizm oceny kompetencji w Kompasie?", size=13, style="B", color=NAVY)

    box_w = 88
    gap_w = 14
    flow_y = 80
    flow_h = 62
    steps_s5 = [
        (
            "Krok A · Obserwacja",
            BLUE_LIGHT,
            NAVY,
            BG,
            BORDER,
            "Wybór zachowań + STAR",
            "Dla każdego wskaźnika przełożony wybiera obserwowalny opis zachowania (lub Brak podstaw) i może zapisać fakt w metodzie STAR jako podstawę rozmowy.",
        ),
        (
            "Krok B · Sugestia",
            PURPLE_LIGHT,
            PURPLE,
            PURPLE_LIGHT,
            PURPLE_BORDER,
            "MeanNearestStrategy",
            "Algorytm liczy średnią z ocenionych wskaźników (min. pokrycie 50%, konserwatywny tie_break: lower) i wskazuje najbliższy poziom na skali (3/5/7 lub 1–9).",
        ),
        (
            "Krok C · Decyzja",
            OK_BG,
            OK_FG,
            OK_BG,
            OK_BORDER,
            "Jawny wybór przełożonego",
            "Sugestia ma status wyłącznie pomocniczy. Przełożony sam wybiera ostateczną ocenę cząstkową — może ją przyjąć lub świadomie skorygować.",
        ),
    ]
    for i, (pill_t, pbg, pfg, cbg, cbr, heading, body) in enumerate(steps_s5):
        bx = 23 + i * (box_w + gap_w)
        pdf.card(bx, flow_y, box_w, flow_h, fill=cbg, border=cbr, radius=3.0)
        pdf.pill(bx + 5, flow_y + 5.5, pill_t, bg=WHITE if cbg != BG else pbg, fg=pfg, font_size=8.2, height=6.2)
        pdf.txt(bx + 5, flow_y + 15.5, box_w - 10, heading, size=11.0, style="B", color=NAVY, line_h=4.8)
        pdf.txt(bx + 5, flow_y + 23.0, box_w - 10, body, size=9.2, color=TEXT, line_h=4.6)
        if i < 2:
            pdf.txt(bx + box_w, flow_y + 26, gap_w, "→", size=18, style="B", color=BLUE if i == 0 else OK_FG, align="C")

    pdf.card(23, 148, W - 46, 16, fill=BG, border=BORDER, radius=2.5, left_bar=BLUE)
    pdf.set_font("UI", "", 9.4)
    pdf.set_text_color(*MUTED)
    pdf.set_xy(29, 151.2)
    pdf.multi_cell(
        W - 56,
        4.6,
        "**Wartość dla urzędu:** Ujednolicenie standardów oceniania między departamentami oraz gotowy, oparty na faktach materiał do rozmowy rozwojowej i obrony oceny przy ewentualnym sprzeciwie.",
        markdown=True,
    )

    # ========================================================================
    # SLAJD 6: LOKALNY ASYSTENT AI (BIELIK + HYBRID RAG)
    # ========================================================================
    pdf.start_content_slide(
        6,
        "05 · Suwerenne i ugruntowane AI",
        "Lokalny Asystent AI: polski Bielik 11B + Hybrid RAG",
        "Jakość AI · 20%",
        PURPLE,
    )

    # Pipeline card
    pdf.card(16, 31, W - 32, 37)
    stages = [
        ("BAZA WIEDZY", "277 chunków", "Ustawa, 2 rozp., KPRM, FAQ, model", BG, BORDER, MUTED),
        ("HYBRID RETRIEVER", "BM25 (0.65) + MiniLM-L12", "Precyzja paragrafów + semantyka", BLUE_LIGHT, BLUE_BORDER, BLUE),
        ("LOKALNY LLM (OLLAMA)", "Bielik 11B v2.3", "Apache 2.0 · 100% on-premise", PURPLE_LIGHT, PURPLE_BORDER, PURPLE),
        ("ODPOWIEDŹ", "Cytowania źródeł", "lub odmowa przy braku danych", OK_BG, OK_BORDER, OK_FG),
    ]
    st_w = 66.5
    ar_w = 9.0
    for i, (k, main, sub, bgc, brc, kc) in enumerate(stages):
        sx = 21 + i * (st_w + ar_w)
        pdf.card(sx, 36.5, st_w, 26, fill=bgc, border=brc, radius=2.5)
        pdf.txt(sx + 2, 39.0, st_w - 4, k, size=7.5, style="B", color=kc, align="C", line_h=3.6)
        pdf.txt(sx + 2, 44.5, st_w - 4, main, size=10.5, style="B", color=NAVY, align="C", line_h=4.6)
        pdf.txt(sx + 2, 51.8, st_w - 4, sub, size=8.0, color=MUTED, align="C", line_h=3.8)
        if i < 3:
            pdf.txt(sx + st_w, 45.5, ar_w, "→", size=14, style="B", color=kc, align="C")

    # Two modes cards
    pdf.card(16, 74, col_w, 97)
    pdf.txt(22, 80, 100, "Tryb 1: Asystent formalny", size=13, style="B", color=BLUE)
    pdf.pill(16 + col_w - 6, 79.5, "Przepisy & FAQ", bg=BLUE_LIGHT, fg=NAVY, font_size=8.2, height=6.4, align_right=True)
    pdf.bullets(
        22,
        92,
        col_w - 12,
        [
            ("Odpowiedzi wyłącznie ze źródeł:", "oparte o ustawę o służbie cywilnej, rozporządzenia 2015/2016, poradniki KPRM, FAQ i model kompetencji."),
            ("Jawne cytowania źródeł:", "użytkownik widzi dokładny akt prawny, paragraf lub poradnik, na którym oparto odpowiedź."),
            ("Zero halucynacji:", "poniżej progu trafności (min_relevance: 0.35) asystent otwarcie komunikuje brak wystarczających informacji w bazie wiedzy."),
        ],
        size=9.8,
        line_h=4.9,
        gap=4.2,
    )

    rx = 16 + col_w + 8
    pdf.card(rx, 74, col_w, 97)
    pdf.txt(rx + 6, 80, 100, "Tryb 2: Asystent rozmowy", size=13, style="B", color=PURPLE)
    pdf.pill(rx + col_w - 6, 79.5, "Kontekst aktywnej oceny", bg=PURPLE_LIGHT, fg=PURPLE, font_size=8.2, height=6.4, align_right=True)
    pdf.bullets(
        rx + 6,
        92,
        col_w - 12,
        [
            ("Kontekst bieżącej oceny:", "analizuje wybrane kryteria, zaznaczone wskaźniki behawioralne i dowody STAR pracownika."),
            ("Spersonalizowany plan rozmowy:", "generuje pytania otwierające, argumentację mocnych stron oraz konstruktywne omówienie obszarów rozwoju."),
            ("Wsparcie IPRZ:", "podpowiada konkretne działania rozwojowe do Indywidualnego Programu Rozwoju Zawodowego."),
        ],
        size=9.8,
        line_h=4.9,
        gap=4.2,
        bullet_color=PURPLE,
    )

    # ========================================================================
    # SLAJD 7: BEZPIECZEŃSTWO AI I GUARDRAILS
    # ========================================================================
    pdf.start_content_slide(
        7,
        "06 · Odpowiedzialne AI w administracji",
        "Zabezpieczenia (Guardrails) i deterministyczne reguły prawa",
        "Bezpieczeństwo & RODO",
        OK_FG,
    )

    c3_w = (W - 32 - 14) / 3
    cards_s7 = [
        (
            16,
            CRIMSON,
            "Ochrona decyzji",
            ERR_BG,
            ERR_FG,
            "RatingDecisionGuardrail",
            "Wykrywa i blokuje próby wymuszenia na AI podjęcia decyzji za przełożonego (np. „Wystaw ocenę 7 pkt dla pracownika”).",
            ERR_BG,
            ERR_FG,
            "Blokada + przypomnienie:\nostateczną ocenę podejmuje wyłącznie przełożony.",
            False,
        ),
        (
            16 + c3_w + 7,
            BLUE,
            "Ochrona PII / RODO",
            BLUE_LIGHT,
            NAVY,
            "PersonalDataGuardrail",
            "Automatycznie wykrywa i maskuje dane wrażliwe przed wysłaniem promptu do modelu LLM oraz w logach aplikacji:",
            BLUE_LIGHT,
            NAVY,
            "PESEL   → [PESEL]\ne-mail  → [EMAIL]\ntelefon → [TELEFON]",
            True,
        ),
        (
            16 + (c3_w + 7) * 2,
            OK_FG,
            "Deterministyczne prawo",
            OK_BG,
            OK_FG,
            "Polityki prawne w kodzie",
            "Krytycznych reguł nie powierzamy LLM — egzekwuje je deterministyczny silnik scoring/policies.py:",
            OK_BG,
            OK_FG,
            "• Cząstkowa 1 pkt = wynik negatywny (§ 11)\n• Brak zdanego egzaminu = brak pozytywnej\n• Wymagane uzasadnienie oceny negatywnej",
            False,
        ),
    ]
    for cx, topc, pill_t, pbg, pfg, heading, body, bbg, bfg, box_text, is_mono in cards_s7:
        pdf.card(cx, 31, c3_w, 120, top_bar=topc)
        pdf.pill(cx + 6, 38.5, pill_t, bg=pbg, fg=pfg, font_size=8.2, height=6.4)
        pdf.txt(cx + 6, 49.0, c3_w - 12, heading, size=12.5, style="B", color=NAVY, line_h=5.2)
        pdf.txt(cx + 6, 57.5, c3_w - 12, body, size=9.6, color=MUTED, line_h=4.7)
        pdf.card(cx + 6, 113, c3_w - 12, 31, fill=bbg, border=None, radius=2.5)
        pdf.txt(
            cx + 10,
            117.5,
            c3_w - 20,
            box_text,
            size=9.2 if not is_mono else 9.0,
            style="B" if not is_mono else "",
            color=bfg,
            line_h=5.2,
            font="Mono" if is_mono else "UI",
        )

    pdf.banner(
        156.5,
        "Pełna suwerenność i darmowe narzędzia:",
        "Bielik 11B (Apache 2.0) + sentence-transformers + BM25 działają lokalnie — 0 zł kosztów licencyjnych i brak transferu danych poza urząd.",
        pill_text="Ślad audytowy RODO",
    )

    # ========================================================================
    # SLAJD 8: ARCHITEKTURA (SOLID & CONFIG-DRIVEN) I JAKOŚĆ
    # ========================================================================
    pdf.start_content_slide(
        8,
        "07 · Technologia i inżynieria",
        "Architektura warstwowa SOLID & Config-Driven",
        "Innowacyjność & Jakość · 20%",
        NAVY,
    )

    # Left: 4 architecture layers
    layers = [
        ("1. Warstwa Prezentacji (Web SPA · Desktop/Tablet)", "Lekki interfejs HTML5 / CSS3 / Vanilla JS serwowany przez FastAPI (blokada < 768px)", NAVY, "UI", BLUE_LIGHT, NAVY),
        ("2. API HTTP & Bezpieczeństwo (FastAPI + Pydantic v2)", "Udokumentowane REST API (/api/v1/docs), JWT + RBAC, SSO, rate limiting", BLUE, "REST", BLUE_LIGHT, NAVY),
        ("3. Serwisy & Silniki Domenowe (DI: AppContainer)", "workflow · scoring · competency · assistant (RAG) · documents (PDF / HTML)", PURPLE, "DIP", PURPLE_LIGHT, PURPLE),
        ("4. Wymienne Adaptery w Registry (YAML Config)", "LLM (Bielik / Ollama / OpenAI / Gemini) · DB (Postgres / SQLite / JSON) · QNT · EZD RP · SMTP", OK_FG, "OCP", OK_BG, OK_FG),
    ]
    ly = 31
    for l_title, l_desc, bar_c, tag, tbg, tfg in layers:
        pdf.card(16, ly, 180, 31.5, left_bar=bar_c)
        pdf.txt(23, ly + 5.5, 146, l_title, size=11.0, style="B", color=NAVY, line_h=4.8)
        pdf.txt(23, ly + 13.0, 146, l_desc, size=9.1, color=MUTED, line_h=4.5)
        pdf.pill(191, ly + 12.0, tag, bg=tbg, fg=tfg, font_size=8.2, height=6.4, align_right=True)
        ly += 35.8

    # Right top: YAML config
    rx = 204
    rw = W - rx - 16
    pdf.card(rx, 31, rw, 68)
    pdf.txt(rx + 6, 36.5, rw - 12, "Sterowanie konfiguracją (Zero Vendor Lock-in)", size=11.5, style="B", color=NAVY, line_h=5.0)
    pdf.txt(
        rx + 6,
        44.5,
        rw - 12,
        "Zmiana modelu AI, bazy danych czy środowiska (dev / test / prod) odbywa się w config/*.yaml lub zmiennych środowiskowych — bez zmian w logice biznesowej:",
        size=9.1,
        color=MUTED,
        line_h=4.4,
    )
    pdf.card(rx + 6, 67, rw - 12, 26, fill=NAVY, border=None, radius=2.5)
    pdf.txt(
        rx + 10,
        71,
        rw - 20,
        "KOMPAS__LLM__PROFILE=bielik\nKOMPAS__RETRIEVER__PROVIDER=hybrid\nKOMPAS__REPOSITORY__PROVIDER=postgres",
        size=8.8,
        color=(207, 228, 255),
        line_h=5.4,
        font="Mono",
    )

    # Right bottom: Quality metrics
    pdf.card(rx, 105, rw, 65.5)
    pdf.txt(rx + 6, 110.5, rw - 12, "Jakość potwierdzona automatycznie", size=11.5, style="B", color=NAVY)
    mw = (rw - 18) / 2
    pdf.card(rx + 6, 120, mw, 26, fill=BG, border=BORDER, radius=2.5)
    pdf.txt(rx + 6, 123.5, mw, "39", size=19, style="B", color=BLUE, align="C", line_h=8.0)
    pdf.txt(rx + 8, 134.0, mw - 4, "Testów (9 plików unit + E2E)", size=8.2, style="B", color=MUTED, align="C", line_h=3.8)

    pdf.card(rx + 12 + mw, 120, mw, 26, fill=BG, border=BORDER, radius=2.5)
    pdf.txt(rx + 12 + mw, 123.5, mw, "≥ 85%", size=19, style="B", color=OK_FG, align="C", line_h=8.0)
    pdf.txt(rx + 14 + mw, 134.0, mw - 4, "Bramka pokrycia pytest-cov", size=8.2, style="B", color=MUTED, align="C", line_h=3.8)

    px_q = rx + 6
    for lbl, bgc, fgc in [("• mypy (typy)", OK_BG, OK_FG), ("• ruff (lint)", OK_BG, OK_FG), ("• Docker + Alembic", BLUE_LIGHT, NAVY)]:
        pw = pdf.pill(px_q, 152.5, lbl, bg=bgc, fg=fgc, font_size=8.0, pad_x=3.0, height=6.4)
        px_q += pw + 2.5

    # ========================================================================
    # SLAJD 9: GOTOWOŚĆ PRODUKCYJNA I INTEGRACJE URZĘDOWE
    # ========================================================================
    pdf.start_content_slide(
        9,
        "08 · Zaimplementowane fundamenty produkcyjne",
        "Gotowość na środowisko Ministerstwa Cyfryzacji",
        "Potencjał wdrożeniowy · 10%",
        OK_FG,
    )

    pdf.card(16, 31, col_w, 121)
    pdf.pill(22, 37, "Już w kodzie · Persistence & Security", bg=OK_BG, fg=OK_FG, font_size=8.2, height=6.4)
    pdf.txt(22, 47, col_w - 12, "Trwałość danych i bezpieczeństwo klasy enterprise", size=12.5, style="B", color=NAVY)
    pdf.bullets(
        22,
        58,
        col_w - 12,
        [
            ("PostgreSQL + Alembic:", "zaimplementowane SqlAlchemyRepository (postgres / sqlite) oraz migracja schematu 001_initial_schema.py."),
            ("Tożsamość i RBAC:", "role supervisor / hr / admin, hashowanie PBKDF2-HMAC-SHA256 oraz gotowe adaptery SSO (OIDC / SAML2) pod AD / gov.pl."),
            ("Utwardzenie API:", "RateLimiter na logowanie i AI, nagłówki bezpieczeństwa, walidator startowy blokujący domyślne sekrety na produkcji (prod.yaml)."),
            ("RODO & Audyt:", "ślad audytowy zmian, maskowanie PII w logach, mechanizm retencji i anonimizacji zakończonych ocen."),
        ],
        size=9.6,
        line_h=4.7,
        gap=3.6,
        bullet_color=OK_FG,
    )

    rx = 16 + col_w + 8
    pdf.card(rx, 31, col_w, 121)
    pdf.pill(rx + 6, 37, "Już w kodzie · Kontrakty integracyjne", bg=BLUE_LIGHT, fg=NAVY, font_size=8.2, height=6.4)
    pdf.txt(rx + 6, 47, col_w - 12, "Integracje z ekosystemem administracji publicznej", size=12.5, style="B", color=NAVY)
    pdf.bullets(
        rx + 6,
        58,
        col_w - 12,
        [
            ("System kadrowy QNT (QntHrGateway):", "przygotowany adapter do synchronizacji struktury organizacyjnej, podległości, dat umów i statusu mianowania."),
            ("EZD RP / EZD PUW (EzdRpArchiveGateway):", "gotowa brama archiwizacji do automatycznego przekazywania arkuszy PDF i metadanych do akt osobowych."),
            ("Powiadomienia SMTP TLS (worker.py):", "dedykowany worker cyklicznych przypomnień o zbliżających się terminach ocen (konfigurowalny reminder_lead_days)."),
            ("Konteneryzacja:", "gotowy Dockerfile i odseparowany profil produkcyjny config/environments/prod.yaml."),
        ],
        size=9.6,
        line_h=4.7,
        gap=3.6,
        bullet_color=BLUE,
    )

    pdf.banner(
        156.5,
        "Transparentność wdrożeniowa:",
        "przed uruchomieniem w MC wymagane jest wyłącznie podpięcie docelowych endpointów API QNT/EZD, serwera IdP (SSO), certyfikatów TLS oraz testów penetracyjnych.",
    )

    # ========================================================================
    # SLAJD 10: PLAN WDROŻENIA + ZAPROSZENIE NA DEMO
    # ========================================================================
    pdf.start_content_slide(
        10,
        "09 · Kierunek rozwoju",
        "Plan wdrożenia w MC i skalowania na administrację",
        "Od prototypu do wdrożenia",
        PURPLE,
    )

    phases = [
        (
            "ETAP 1 · TYGODNIE 1–4",
            BLUE,
            BLUE_LIGHT,
            "Infrastruktura i audyt w MC",
            [
                ("Środowisko produkcyjne:", "uruchomienie w MC (PostgreSQL, reverse proxy TLS, Vault)."),
                ("Tożsamość:", "podpięcie korporacyjnego SSO (AD / gov.pl)."),
                ("Suwerenne AI:", "wdrożenie lokalnego serwera GPU dla Bielik 11B + testy bezpieczeństwa i WCAG."),
            ],
        ),
        (
            "ETAP 2 · MIESIĄCE 2–3",
            PURPLE,
            PURPLE_LIGHT,
            "Integracje i pilotaż w BDG",
            [
                ("Systemy urzędowe:", "produkcyjne podłączenie API QNT (kadry) oraz EZD RP (akta osobowe)."),
                ("Automatyzacja:", "uruchomienie workera przypomnień SMTP TLS."),
                ("Pilotaż:", "wdrożenie z przełożonymi i HR w MC oraz kalibracja bazy RAG."),
            ],
        ),
        (
            "ETAP 3 · MIESIĄCE 4+",
            OK_FG,
            OK_BG,
            "Skalowanie na służbę cywilną",
            [
                ("Multi-urząd (YAML):", "udostępnienie innym ministerstwom i urzędom administracji rządowej."),
                ("Analityka:", "raporty luk kompetencyjnych i potrzeb szkoleniowych dla BDG / KPRM."),
                ("Rozwój IPRZ:", "rozbudowa o moduł monitorowania realizacji celów rozwojowych."),
            ],
        ),
    ]
    for i, (tag, topc, tbg, heading, items) in enumerate(phases):
        px = 16 + i * (c3_w + 7)
        pdf.card(px, 31, c3_w, 97, top_bar=topc)
        pdf.pill(px + 6, 38, tag, bg=tbg, fg=topc, font_size=8.0, height=6.2)
        pdf.txt(px + 6, 48.0, c3_w - 12, heading, size=12.0, style="B", color=NAVY)
        pdf.bullets(px + 6, 58.0, c3_w - 12, items, size=9.3, line_h=4.6, gap=3.2, bullet_color=topc)

    # Bottom Demo CTA
    pdf.card(16, 134, W - 32, 37, fill=NAVY, border=None, radius=3.5)
    pdf.txt(23, 138.5, 220, "CZAS NA PREZENTACJĘ DZIAŁAJĄCEGO PROTOTYPU", size=8.5, style="B", color=SKY, line_h=4.0)
    pdf.txt(23, 144.2, 235, "Zapraszamy na Demo na żywo (5 min) + Q&A z Bielikiem!", size=16.5, style="B", color=WHITE, line_h=7.0)
    pdf.txt(
        23,
        154.0,
        245,
        "Upload OSP → Arkusz C i kryteria → Wskaźniki + STAR + sugestia → Asystent rozmowy i formalny (Bielik RAG) → Wniosek o stopień i PDF → Panel HR",
        size=9.2,
        color=(203, 216, 230),
        line_h=4.4,
    )
    pdf.pill(W - 23, 147.5, "Kompas Kompetencji", bg=NAVY_MID, fg=WHITE, font_size=10.0, pad_x=6.0, height=9.0, align_right=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))


if __name__ == "__main__":
    out = Path("docs/Kompas_Kompetencji_Prezentacja.pdf")
    build_pdf(out)
    print(f"Generated: {out.resolve()} ({out.stat().st_size / 1024:.1f} KB)")
