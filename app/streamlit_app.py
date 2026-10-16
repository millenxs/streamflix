"""Streamlit demo for StreamFlix recommendations."""

from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st

DEFAULT_API_URL = os.getenv("STREAMFLIX_API_URL", "http://localhost:8000")
FEEDBACK_TYPES = ("impression", "click", "play", "complete")
FEEDBACK_LABELS = {
    "impression": ":material/visibility: Impression",
    "click": ":material/touch_app: Click",
    "play": ":material/play_arrow: Assistir",
    "complete": ":material/check_circle: Complete",
}


def fetch_recommendations(api_url: str, user_id: int, limit: int) -> dict[str, Any]:
    """Fetch recommendations from the StreamFlix API."""
    response = requests.get(
        f"{api_url.rstrip('/')}/recommendations/{user_id}",
        params={"limit": limit},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def build_feedback_payload(user_id: int, item: dict[str, Any], feedback_type: str) -> dict[str, Any]:
    """Build the feedback payload accepted by the StreamFlix API."""
    payload = {
        "user_id": user_id,
        "content_id": int(item["content_id"]),
        "feedback_type": feedback_type,
    }
    if item.get("recommendation_id"):
        payload["recommendation_id"] = item["recommendation_id"]
    return payload


def send_feedback(api_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Send recommendation feedback to the StreamFlix API."""
    response = requests.post(f"{api_url.rstrip('/')}/feedback", json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


def content_subtitle(item: dict[str, Any]) -> str:
    """Return a compact movie/series metadata subtitle."""
    parts = [
        item.get("primary_genre") or "Catálogo",
        str(item.get("release_year")) if item.get("release_year") else None,
        str(item.get("content_type") or "content").title(),
    ]
    return " • ".join(part for part in parts if part)


def recommendation_reason(item: dict[str, Any]) -> str:
    """Explain why an item appears in the recommendation row."""
    genre = item.get("primary_genre") or "conteúdos populares"
    algorithm = item.get("algorithm", "modelo")
    if algorithm == "hybrid":
        return f"Porque combina seu histórico com conteúdos de {genre} em alta."
    if algorithm == "warehouse_popularity":
        return f"Porque está entre os conteúdos de {genre} com melhor desempenho."
    return "Recomendação de demonstração enquanto o pipeline carrega dados reais."


def render_poster(item: dict[str, Any]) -> None:
    """Render poster imagery when available, with a text fallback."""
    title = item.get("title") or f"Content {item['content_id']}"
    if item.get("poster_url"):
        st.image(item["poster_url"], alt=f"Poster de {title}", width="stretch")
    else:
        st.markdown(f"##### {item.get('thumbnail_variant', 'default')}")
        st.caption("Thumbnail variant")
    st.metric("Score", f"{float(item['score']):.4f}")
    st.badge(item.get("algorithm", "hybrid"))


def render_recommendation_card(api_url: str, user_id: int, item: dict[str, Any]) -> None:
    """Render one product-style recommendation card and its feedback buttons."""
    title = item.get("title") or f"Content {item['content_id']}"
    with st.container(border=True):
        poster_col, detail_col = st.columns([1, 3], vertical_alignment="center")
        with poster_col:
            render_poster(item)
        with detail_col:
            st.subheader(title)
            st.caption(content_subtitle(item))
            st.write(recommendation_reason(item))
            st.write(f"Content ID `{item['content_id']}`")
            if item.get("vote_average") is not None:
                st.write(f"TMDB rating: `{float(item['vote_average']):.1f}`")
            if item.get("overview"):
                st.caption(item["overview"])
            if item.get("tmdb_url"):
                st.link_button("Abrir no TMDB", item["tmdb_url"], width="content")

            feedback_cols = st.columns(len(FEEDBACK_TYPES))
            for column, feedback_type in zip(feedback_cols, FEEDBACK_TYPES, strict=True):
                key = f"{user_id}-{item['content_id']}-{feedback_type}"
                if column.button(FEEDBACK_LABELS[feedback_type], key=key, width="stretch"):
                    payload = build_feedback_payload(user_id, item, feedback_type)
                    result = send_feedback(api_url, payload)
                    st.success(f"Feedback enviado: {feedback_type} ({result['event_id']})")


def main() -> None:
    st.set_page_config(page_title="StreamFlix Demo", page_icon="🎬", layout="wide")
    st.title("StreamFlix home")
    st.caption("Experiência de produto para recomendações personalizadas, A/B testing e feedback loop.")

    with st.sidebar:
        st.header("Configuração")
        api_url = st.text_input("API URL", value=DEFAULT_API_URL)
        user_id = st.number_input("User ID", min_value=1, value=1, step=1)
        limit = st.slider("Quantidade de recomendações", min_value=1, max_value=20, value=10)
        fetch = st.button("Buscar recomendações", type="primary")

    if fetch:
        try:
            st.session_state["recommendations"] = fetch_recommendations(api_url, int(user_id), int(limit))
        except requests.RequestException as exc:
            st.error(f"Erro ao buscar recomendações: {exc}")

    data = st.session_state.get("recommendations")
    if not data:
        st.info("Clique em 'Buscar recomendações' para iniciar a demo.")
        return

    st.subheader(f"Usuário {data['user_id']}")
    st.write(f"**Experimento:** `{data['experiment_variant']}`")

    recommendations = data.get("recommendations", [])
    if not recommendations:
        st.warning("Nenhuma recomendação retornada para este usuário.")
        return

    for item in recommendations:
        render_recommendation_card(api_url, int(data["user_id"]), item)


if __name__ == "__main__":
    main()
