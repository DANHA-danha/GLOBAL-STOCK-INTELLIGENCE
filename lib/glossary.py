"""용어 사전: 어느 화면에서든 term("PER")처럼 부르면 뜻을 보여줘요."""
from __future__ import annotations

import hashlib
from datetime import date

import streamlit as st
import yaml

from lib.data import ROOT

CATEGORIES = ["기본", "기업 분석", "경제 지표", "채권·자본시장", "투자·수급", "시장"]


@st.cache_data
def all_terms() -> list[dict]:
    return yaml.safe_load((ROOT / "data" / "glossary.yaml").read_text(encoding="utf-8"))


def get(name: str) -> dict | None:
    for t in all_terms():
        if t["term"] == name:
            return t
    return None


def card(t: dict, show_related: bool = True) -> None:
    """용어 하나를 카드처럼 보여줘요."""
    st.markdown(f"**{t['term']}** <span style='color:gray;font-size:0.85em'>{t.get('en', '')}</span>", unsafe_allow_html=True)
    st.write(t["short"])
    if t.get("detail"):
        st.caption(t["detail"])
    if t.get("formula"):
        st.latex(t["formula"])
    if t.get("example"):
        st.info(f"예시: {t['example']}", icon=":material/calculate:")
    if t.get("caution"):
        st.warning(t["caution"], icon=":material/lightbulb:")
    if show_related and t.get("related"):
        st.caption("같이 보면 좋은 용어: " + ", ".join(t["related"]))


def term(name: str, label: str | None = None) -> None:
    """버튼처럼 생긴 용어. 누르면 그 자리에서 뜻이 펼쳐져요."""
    t = get(name)
    if not t:
        st.write(label or name)
        return
    with st.popover(label or name, icon=":material/help:"):
        card(t)


def today_term() -> dict:
    """날짜마다 바뀌는 오늘의 용어."""
    terms = all_terms()
    h = int(hashlib.md5(date.today().isoformat().encode()).hexdigest(), 16)
    return terms[h % len(terms)]
