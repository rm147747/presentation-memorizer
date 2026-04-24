"""
Streamlit frontend — Memorização de Apresentações

Fluxo:
  1. Nova Apresentação → cola/upload texto → grava referência
  2. Treinar → aplica degradação → grava tentativa → vê diff visual
  3. Relatório → baixa PDF ou JSON
"""
from __future__ import annotations

import io
from pathlib import Path

import requests
import streamlit as st

API = "http://localhost:8000"

st.set_page_config(
    page_title="Memorizar Apresentação",
    page_icon="🎤",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .diff-ok      { color: #27ae60; font-weight: bold; }
    .diff-omit    { color: #e74c3c; text-decoration: line-through; }
    .diff-sub     { color: #e67e22; font-weight: bold; }
    .diff-insert  { color: #8e44ad; font-style: italic; }
    .heat-dominated { background: #d5f5e3; border-radius: 3px; padding: 1px 3px; }
    .heat-unstable  { background: #fdebd0; border-radius: 3px; padding: 1px 3px; }
    .heat-critical  { background: #fadbd8; border-radius: 3px; padding: 1px 3px; }
    .metric-box { background: #f8f9fa; border-radius: 8px; padding: 12px; text-align: center; }
    </style>
    """,
    unsafe_allow_html=True,
)

LEVEL_LABEL = {
    1: "Texto completo",
    2: "Texto com lacunas (30%)",
    3: "Apenas primeira palavra",
    4: "Tela em branco",
}


# ── Navigation ────────────────────────────────────────────────────────────────
page = st.sidebar.radio(
    "Navegação",
    ["📄 Nova Apresentação", "🎯 Treinar", "📊 Relatório"],
)

if "pres_id" in st.session_state:
    st.sidebar.success(f"Apresentação ativa: #{st.session_state['pres_id']}")
if "session_id" in st.session_state:
    st.sidebar.info(f"Sessão ativa: #{st.session_state['session_id']}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _post(path: str, **kwargs) -> requests.Response:
    return requests.post(f"{API}{path}", **kwargs)


def _get(path: str, **kwargs) -> requests.Response:
    return requests.get(f"{API}{path}", **kwargs)


def _api_error(resp: requests.Response) -> None:
    try:
        detail = resp.json().get("detail", resp.text)
    except Exception:
        detail = resp.text
    st.error(f"Erro {resp.status_code}: {detail}")


def _render_diff(omitted: list[str], substituted: list[tuple], transcript: str) -> None:
    """Render colour-coded diff summary."""
    if not omitted and not substituted:
        st.success("Nenhum erro detectado.")
        return

    parts: list[str] = []
    sub_dict = dict(substituted)

    for word in transcript.split():
        w = word.lower().strip(".,;:!?")
        if w in omitted:
            parts.append(f'<span class="diff-omit">{word}</span>')
        elif w in sub_dict:
            correct = sub_dict[w]
            parts.append(f'<span class="diff-sub">{word} [{correct}]</span>')
        else:
            parts.append(f'<span class="diff-ok">{word}</span>')

    st.markdown(" ".join(parts), unsafe_allow_html=True)


def _render_heat_text(segments: list[dict]) -> None:
    """Render original text coloured by difficulty score."""
    parts: list[str] = []
    for seg in segments:
        score = seg["difficulty_score"]
        css = (
            "heat-dominated" if score <= 0.2
            else "heat-unstable" if score <= 0.5
            else "heat-critical"
        )
        text = seg["text"][:120] + ("…" if len(seg["text"]) > 120 else "")
        parts.append(f'<span class="{css}">{text}</span>')
    st.markdown("<br>".join(parts), unsafe_allow_html=True)


# ── Page: Nova Apresentação ───────────────────────────────────────────────────
if page == "📄 Nova Apresentação":
    st.header("1. Apresentação")

    title = st.text_input("Título")
    col_text, col_file = st.columns([3, 1])
    with col_text:
        text_val = st.text_area("Cole o texto aqui", height=260, key="paste_area")
    with col_file:
        st.write("")
        st.write("")
        upload = st.file_uploader("Ou envie .txt", type=["txt"])
        if upload:
            text_val = upload.read().decode("utf-8")
            st.session_state["paste_area"] = text_val
            st.rerun()

    if st.button("Salvar Apresentação", type="primary", disabled=not (title and text_val)):
        resp = _post("/presentations/", json={"title": title, "text": text_val})
        if resp.ok:
            d = resp.json()
            st.session_state["pres_id"] = d["id"]
            st.success(f"Salvo! ID {d['id']} | {d['segment_count']} segmentos")
        else:
            _api_error(resp)

    st.divider()
    st.header("2. Gravação de Referência")
    st.caption(
        "Leia o texto em voz alta completamente. "
        "O sistema transcreve com Whisper e alinha cada palavra com seu timestamp."
    )

    audio_bytes = st.audio_input("Gravar agora", key="ref_recorder")
    ref_upload = st.file_uploader("Ou envie arquivo de áudio", type=["wav", "mp3", "m4a"], key="ref_file")

    audio_source = audio_bytes or ref_upload
    pres_id = st.session_state.get("pres_id")

    if audio_source and pres_id and st.button("Transcrever Referência", type="primary"):
        payload = (
            audio_source.read() if hasattr(audio_source, "read")
            else audio_source.getvalue()
        )
        with st.spinner("Transcrevendo com Whisper…"):
            resp = _post(
                f"/presentations/{pres_id}/reference-audio",
                files={"audio": ("reference.wav", io.BytesIO(payload), "audio/wav")},
            )
        if resp.ok:
            d = resp.json()
            st.success(f"Referência salva. Idioma: {d['language']} | Segmentos: {d['segments']}")
            st.text_area("Transcrição", d["transcript"], height=120)
        else:
            _api_error(resp)


# ── Page: Treinar ─────────────────────────────────────────────────────────────
elif page == "🎯 Treinar":
    st.header("Modo de Treino")

    # ── Config bar ────────────────────────────────────────────────────────────
    cfg_cols = st.columns([1, 1, 1, 2])
    with cfg_cols[0]:
        pres_id = st.number_input(
            "Apresentação ID",
            min_value=1,
            step=1,
            value=st.session_state.get("pres_id", 1),
        )
        st.session_state["pres_id"] = pres_id

    with cfg_cols[1]:
        level = st.selectbox(
            "Nível",
            options=[1, 2, 3, 4],
            format_func=lambda l: f"Nível {l} — {LEVEL_LABEL[l]}",
        )

    with cfg_cols[2]:
        if st.button("Nova Sessão", type="primary"):
            resp = _post("/sessions/", params={"presentation_id": pres_id, "level": level})
            if resp.ok:
                st.session_state["session_id"] = resp.json()["session_id"]
                st.session_state.pop("degraded", None)
                st.success(f"Sessão #{st.session_state['session_id']} criada")
            else:
                _api_error(resp)

    with cfg_cols[3]:
        seg_idx = st.number_input("Segmento", min_value=0, step=1)

    st.divider()

    # ── Text display ──────────────────────────────────────────────────────────
    col_orig, col_deg = st.columns(2)
    with col_orig:
        st.subheader("Texto de Referência")
        original = st.text_area("(cole para degradar)", height=180, key="orig_input")
        if st.button("Aplicar Degradação") and original:
            resp = _post("/degrade", json={"text": original, "level": level, "seed": 42})
            if resp.ok:
                st.session_state["degraded"] = resp.json()["text"]
            else:
                _api_error(resp)

    with col_deg:
        st.subheader(f"Texto Degradado — {LEVEL_LABEL[level]}")
        if "degraded" in st.session_state:
            if level == 4:
                st.info("Tela em branco — tente sem apoio visual.")
            else:
                st.text_area(
                    "Estude antes de gravar",
                    st.session_state["degraded"],
                    height=180,
                    disabled=True,
                )
        else:
            st.caption("Cole o texto e clique em «Aplicar Degradação».")

    st.divider()

    # ── Attempt recording ─────────────────────────────────────────────────────
    st.subheader("Gravar Tentativa")
    st.caption("Fale o trecho de memória. Não leia o texto enquanto grava.")

    rec_col, upload_col = st.columns(2)
    with rec_col:
        attempt_audio = st.audio_input("Gravar agora", key="attempt_recorder")
    with upload_col:
        attempt_file = st.file_uploader(
            "Ou envie arquivo", type=["wav", "mp3", "m4a"], key="attempt_file"
        )

    attempt_source = attempt_audio or attempt_file
    session_id = st.session_state.get("session_id")

    if attempt_source and session_id and st.button("Analisar Tentativa", type="primary"):
        payload = (
            attempt_source.read() if hasattr(attempt_source, "read")
            else attempt_source.getvalue()
        )
        with st.spinner("Transcrevendo e comparando…"):
            resp = _post(
                f"/sessions/{session_id}/attempt",
                params={"segment_index": seg_idx},
                files={"audio": ("attempt.wav", io.BytesIO(payload), "audio/wav")},
            )

        if resp.ok:
            d = resp.json()
            st.session_state["last_result"] = d

    if "last_result" in st.session_state:
        d = st.session_state["last_result"]

        # ── Metrics ───────────────────────────────────────────────────────────
        m1, m2, m3 = st.columns(3)
        m1.metric("Erros totais", d["error_count"])
        m2.metric("Hesitações", d["hesitation_count"])
        m3.metric("Taxa de erro", f"{d['error_ratio']:.0%}")

        # ── Diff visual ───────────────────────────────────────────────────────
        st.subheader("Análise Palavra a Palavra")
        _render_diff(d["omitted"], d["substituted"], d["transcript"])

        if d["omitted"]:
            st.write("**Palavras omitidas:**", ", ".join(d["omitted"]))
        if d["substituted"]:
            pairs = " · ".join(f"`{o}` → `{e}`" for o, e in d["substituted"])
            st.write("**Substituições:**", pairs)
        if d["hesitation_points"]:
            pts = ", ".join(f"{p:.1f}s" for p in d["hesitation_points"])
            st.write("**Hesitações em:**", pts)

    # ── Spaced repetition agenda ──────────────────────────────────────────────
    st.divider()
    if st.button("Ver Agenda de Repetição"):
        resp = _get(f"/presentations/{pres_id}/schedule")
        if resp.ok:
            d = resp.json()
            s = d["summary"]
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("Segmentos totais", s["total_segments"])
            mc2.metric("Dominados", s["dominated"])
            mc3.metric("% dominado", f"{s['pct_dominated']}%")

            if d["repeat_segments"]:
                st.warning(f"**{len(d['repeat_segments'])} segmento(s) para revisar:**")
                for seg in d["repeat_segments"]:
                    bar_val = min(seg["score"], 1.0)
                    st.progress(bar_val, text=f"#{seg['index']} · score {seg['score']:.2f} — {seg['text']}")
            else:
                st.success("Todos os segmentos dominados!")
        else:
            _api_error(resp)


# ── Page: Relatório ───────────────────────────────────────────────────────────
elif page == "📊 Relatório":
    st.header("Relatório de Progresso")

    pres_id = st.number_input(
        "Apresentação ID",
        min_value=1,
        step=1,
        value=st.session_state.get("pres_id", 1),
        key="rep_pres",
    )
    fmt = st.radio("Formato", ["pdf", "json"], horizontal=True)

    if st.button("Gerar Relatório", type="primary"):
        with st.spinner("Gerando…"):
            resp = _get(f"/presentations/{pres_id}/report", params={"fmt": fmt})
        if resp.ok:
            mime = "application/pdf" if fmt == "pdf" else "application/json"
            st.download_button(
                label=f"⬇ Baixar {fmt.upper()}",
                data=resp.content,
                file_name=f"report_{pres_id}.{fmt}",
                mime=mime,
                type="primary",
            )
            st.success("Relatório pronto.")

            if fmt == "json":
                import json
                data = resp.json()
                st.subheader("Visualização Rápida")
                col_l, col_r = st.columns(2)
                with col_l:
                    st.metric("Sessões", len(data.get("sessions", [])))
                with col_r:
                    segs = data.get("segments", [])
                    dom = sum(1 for s in segs if s["difficulty_score"] <= 0.2)
                    st.metric("Segmentos dominados", f"{dom}/{len(segs)}")

                st.subheader("Mapa de Calor")
                _render_heat_text(segs)
        else:
            _api_error(resp)
