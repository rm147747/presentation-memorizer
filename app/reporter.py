"""
Progress report generation — PDF (reportlab) and JSON.

PDF layout:
  1. Título + data de geração
  2. Resumo geral (sessões, tempo, % dominado)
  3. Mapa de calor textual (verde / amarelo / vermelho por score)
  4. Trechos críticos (top 5)
  5. Curva de evolução (tabela de scores por sessão)
  6. Palavras mais trocadas

JSON: dados brutos para integração externa.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

DOMINATED_THRESHOLD = 0.2
UNSTABLE_THRESHOLD = 0.5

_COLOUR_MAP = {
    "dominated": "#27ae60",
    "unstable":  "#e67e22",
    "critical":  "#e74c3c",
}


@dataclass
class SessionSummary:
    session_id: str
    started_at: str
    duration_seconds: float
    mean_score: float


@dataclass
class ReportData:
    presentation_title: str
    sessions: list[SessionSummary]
    # each dict: {"text": str, "difficulty_score": float, "attempts": int}
    segments: list[dict[str, Any]]
    # top substitution pairs: [(original_word, error_word), ...]
    word_pairs: list[tuple[str, str]]
    generated_at: str = ""

    def __post_init__(self) -> None:
        if not self.generated_at:
            self.generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── Public API ────────────────────────────────────────────────────────────────

def export_json(data: ReportData, path: str | Path) -> Path:
    out = Path(path)
    out.write_text(json.dumps(asdict(data), indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def export_pdf(data: ReportData, path: str | Path) -> Path:
    out = Path(path)
    doc = SimpleDocTemplate(
        str(out),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    story = _build_story(data)
    doc.build(story)
    return out


# ── Story builder ─────────────────────────────────────────────────────────────

def _build_story(data: ReportData) -> list:
    styles = getSampleStyleSheet()
    _add_custom_styles(styles)
    story: list[Any] = []

    # ── Title ─────────────────────────────────────────────────────────────────
    story.append(Paragraph(f"Relatório: {data.presentation_title}", styles["ReportTitle"]))
    story.append(Paragraph(f"Gerado em {data.generated_at}", styles["Normal"]))
    story.append(Spacer(1, 0.6 * cm))

    # ── General summary ───────────────────────────────────────────────────────
    story.append(Paragraph("Resumo Geral", styles["Heading2"]))
    dominated = sum(1 for s in data.segments if s["difficulty_score"] <= DOMINATED_THRESHOLD)
    total_segs = len(data.segments) or 1
    pct_dom = round(dominated / total_segs * 100)
    total_time_min = int(sum(s.duration_seconds for s in data.sessions) // 60)

    story.append(
        Paragraph(
            f"Sessões: <b>{len(data.sessions)}</b> &nbsp;|&nbsp; "
            f"Tempo total: <b>{total_time_min} min</b> &nbsp;|&nbsp; "
            f"Texto dominado: <b>{pct_dom}%</b>",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 0.5 * cm))

    # ── Heat map ──────────────────────────────────────────────────────────────
    story.append(Paragraph("Mapa de Calor Textual", styles["Heading2"]))
    for seg in data.segments:
        colour = _score_colour(seg["difficulty_score"])
        story.append(
            Paragraph(
                f'<font color="{colour}">{seg["text"]}</font>',
                styles["HeatText"],
            )
        )
    story.append(Spacer(1, 0.5 * cm))

    # ── Critical segments ─────────────────────────────────────────────────────
    story.append(Paragraph("Trechos Críticos (Top 5)", styles["Heading2"]))
    critical = sorted(data.segments, key=lambda s: s["difficulty_score"], reverse=True)[:5]
    for rank, seg in enumerate(critical, 1):
        excerpt = seg["text"][:150] + ("…" if len(seg["text"]) > 150 else "")
        story.append(
            Paragraph(
                f'<b>{rank}.</b> Score <font color="{_score_colour(seg["difficulty_score"])}">'
                f'{seg["difficulty_score"]:.2f}</font> — {excerpt}',
                styles["Normal"],
            )
        )
    story.append(Spacer(1, 0.5 * cm))

    # ── Session evolution table ───────────────────────────────────────────────
    if data.sessions:
        story.append(Paragraph("Curva de Evolução por Sessão", styles["Heading2"]))
        table_data = [["Sessão", "Data", "Duração (min)", "Score Médio"]]
        for s in data.sessions:
            table_data.append([
                s.session_id,
                s.started_at[:10],
                f"{s.duration_seconds / 60:.1f}",
                f"{s.mean_score:.3f}",
            ])
        tbl = Table(table_data, colWidths=[3 * cm, 4 * cm, 4 * cm, 4 * cm])
        tbl.setStyle(_table_style())
        story.append(tbl)
        story.append(Spacer(1, 0.5 * cm))

    # ── Word substitution pairs ───────────────────────────────────────────────
    if data.word_pairs:
        story.append(Paragraph("Palavras Mais Trocadas", styles["Heading2"]))
        pair_data = [["Palavra Original", "Erro Mais Frequente"]] + [
            [orig, err] for orig, err in data.word_pairs[:10]
        ]
        tbl = Table(pair_data, colWidths=[8 * cm, 8 * cm])
        tbl.setStyle(_table_style())
        story.append(tbl)

    return story


# ── Helpers ───────────────────────────────────────────────────────────────────

def _score_colour(score: float) -> str:
    if score <= DOMINATED_THRESHOLD:
        return _COLOUR_MAP["dominated"]
    if score <= UNSTABLE_THRESHOLD:
        return _COLOUR_MAP["unstable"]
    return _COLOUR_MAP["critical"]


def _add_custom_styles(styles) -> None:
    styles.add(ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=18,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        "HeatText",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=3,
    ))


def _table_style() -> TableStyle:
    return TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor("#2c3e50")),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, colors.HexColor("#ecf0f1")]),
        ("GRID",          (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])
