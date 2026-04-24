"""FastAPI backend for the presentation memorization system."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.aligner import align, annotate_difficulty
from app.database import Attempt, Presentation, Segment, TrainingSession, make_session_factory
from app.degrader import degrade
from app.differ import compare
from app.reporter import ReportData, SessionSummary, export_json, export_pdf
from app.scheduler import Schedule, SegmentStats
from app.transcriber import transcribe

AUDIO_DIR = Path("data/audio")
REPORT_DIR = Path("data/reports")
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Presentation Memorizer", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_SessionFactory = make_session_factory()


# ── Schemas ───────────────────────────────────────────────────────────────────

class PresentationIn(BaseModel):
    title: str
    text: str


class DegradeIn(BaseModel):
    text: str
    level: int
    seed: int | None = None


# ── Presentations ─────────────────────────────────────────────────────────────

@app.post("/presentations/", status_code=201)
def create_presentation(body: PresentationIn):
    paragraphs = [p.strip() for p in body.text.split("\n") if p.strip()]
    with _SessionFactory() as db:
        pres = Presentation(title=body.title, text=body.text)
        db.add(pres)
        db.flush()
        for i, para in enumerate(paragraphs):
            db.add(Segment(presentation_id=pres.id, segment_index=i, text=para))
        db.commit()
        return {"id": pres.id, "title": pres.title, "segment_count": len(paragraphs)}


@app.post("/presentations/{pres_id}/reference-audio")
async def upload_reference_audio(pres_id: int, audio: UploadFile = File(...)):
    with _SessionFactory() as db:
        pres = db.get(Presentation, pres_id)
        if not pres:
            raise HTTPException(404, "Presentation not found")

        suffix = Path(audio.filename).suffix if audio.filename else ".wav"
        audio_path = AUDIO_DIR / f"ref_{pres_id}{suffix}"
        with audio_path.open("wb") as f:
            shutil.copyfileobj(audio.file, f)

        tx = transcribe(audio_path)
        pres.reference_audio = str(audio_path)
        db.commit()

        # Align transcript against original text to get per-word timestamps
        paragraphs = [p.strip() for p in pres.text.split("\n") if p.strip()]
        aligned = align(pres.text, tx.segments)
        matched = sum(1 for a in aligned if a.matched)

        return {
            "transcript": tx.text,
            "segments": len(tx.segments),
            "language": tx.language,
            "aligned_words": len(aligned),
            "matched_words": matched,
            "coverage_pct": round(matched / len(aligned) * 100, 1) if aligned else 0,
        }


# ── Degradation ───────────────────────────────────────────────────────────────

@app.post("/degrade")
def degrade_text(body: DegradeIn):
    if body.level not in (1, 2, 3, 4):
        raise HTTPException(400, "level must be 1–4")
    result = degrade(body.text, body.level, seed=body.seed)
    return {"text": result.text, "level": result.level, "blanked_indices": result.blanked_indices}


# ── Sessions ──────────────────────────────────────────────────────────────────

@app.post("/sessions/", status_code=201)
def start_session(presentation_id: int, level: int):
    with _SessionFactory() as db:
        pres = db.get(Presentation, presentation_id)
        if not pres:
            raise HTTPException(404, "Presentation not found")
        sess = TrainingSession(presentation_id=presentation_id, level=level)
        db.add(sess)
        db.commit()
        return {"session_id": sess.id}


@app.post("/sessions/{session_id}/attempt")
async def record_attempt(
    session_id: int,
    segment_index: int = Query(...),
    audio: UploadFile = File(...),
):
    with _SessionFactory() as db:
        sess = db.get(TrainingSession, session_id)
        if not sess:
            raise HTTPException(404, "Session not found")

        seg = (
            db.query(Segment)
            .filter_by(presentation_id=sess.presentation_id, segment_index=segment_index)
            .first()
        )
        if not seg:
            raise HTTPException(404, "Segment not found")

        suffix = Path(audio.filename).suffix if audio.filename else ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            shutil.copyfileobj(audio.file, tmp)
            tmp_path = Path(tmp.name)

        try:
            tx = transcribe(tmp_path)
            diff = compare(seg.text, tx.text, tx.segments)
        finally:
            tmp_path.unlink(missing_ok=True)

        db.add(Attempt(
            session_id=session_id,
            segment_index=segment_index,
            attempt_text=tx.text,
            error_count=diff.error_count,
            hesitation_count=diff.hesitation_count,
        ))
        seg.attempts += 1
        seg.total_errors += diff.error_count
        seg.total_hesitations += diff.hesitation_count
        db.commit()

        return {
            "transcript": tx.text,
            "error_count": diff.error_count,
            "hesitation_count": diff.hesitation_count,
            "omitted": diff.omitted,
            "substituted": diff.substituted,
            "hesitation_points": diff.hesitation_points,
            "error_ratio": diff.error_ratio,
        }


# ── Schedule ──────────────────────────────────────────────────────────────────

@app.get("/presentations/{pres_id}/schedule")
def get_schedule(pres_id: int):
    with _SessionFactory() as db:
        segs = db.query(Segment).filter_by(presentation_id=pres_id).order_by(Segment.segment_index).all()
        if not segs:
            raise HTTPException(404, "No segments found")

        schedule = Schedule(
            segments=[
                SegmentStats(
                    segment_index=s.segment_index,
                    text=s.text,
                    attempts=s.attempts,
                    total_errors=s.total_errors,
                    total_hesitations=s.total_hesitations,
                )
                for s in segs
            ]
        )
        repeat = schedule.next_cycle()
        return {
            "summary": schedule.summary(),
            "repeat_segments": [
                {"index": s.segment_index, "score": s.difficulty_score, "text": s.text[:100]}
                for s in repeat
            ],
        }


# ── Reports ───────────────────────────────────────────────────────────────────

@app.get("/presentations/{pres_id}/report")
def download_report(pres_id: int, fmt: str = Query("pdf", pattern="^(pdf|json)$")):
    with _SessionFactory() as db:
        pres = db.get(Presentation, pres_id)
        if not pres:
            raise HTTPException(404, "Presentation not found")

        sessions = db.query(TrainingSession).filter_by(presentation_id=pres_id).all()
        segs = db.query(Segment).filter_by(presentation_id=pres_id).order_by(Segment.segment_index).all()

        # Aggregate most-swapped word pairs from all attempts
        from collections import Counter
        pair_counts: Counter = Counter()
        for sess in sessions:
            for att in sess.attempts:
                # Stored as plaintext; re-diff to extract pairs
                seg = next((s for s in segs if s.segment_index == att.segment_index), None)
                if seg and att.attempt_text:
                    diff = compare(seg.text, att.attempt_text)
                    for orig, err in diff.substituted:
                        pair_counts[(orig, err)] += 1

        word_pairs = [list(pair) for pair, _ in pair_counts.most_common(10)]

        data = ReportData(
            presentation_title=pres.title,
            sessions=[
                SessionSummary(
                    session_id=str(s.id),
                    started_at=str(s.started_at),
                    duration_seconds=(
                        (s.completed_at - s.started_at).total_seconds()
                        if s.completed_at else 0.0
                    ),
                    mean_score=s.mean_score or 0.0,
                )
                for s in sessions
            ],
            segments=[
                {"text": s.text, "difficulty_score": s.difficulty_score, "attempts": s.attempts}
                for s in segs
            ],
            word_pairs=word_pairs,
        )

    if fmt == "json":
        path = export_json(data, REPORT_DIR / f"report_{pres_id}.json")
        return FileResponse(str(path), media_type="application/json", filename=path.name)

    path = export_pdf(data, REPORT_DIR / f"report_{pres_id}.pdf")
    return FileResponse(str(path), media_type="application/pdf", filename=path.name)
