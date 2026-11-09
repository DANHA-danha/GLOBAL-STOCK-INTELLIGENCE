import random

import streamlit as st

from lib import glossary, ui

st.title("용어 튜터")
st.caption("뉴스와 공시에 자주 나오는 말을 쉬운 말로 풀었어요. 다른 화면의 물음표 버튼을 눌러도 같은 설명이 나와요.")

terms = glossary.all_terms()
tab_dict, tab_quiz = st.tabs(["용어 사전", "퀴즈"])

# ---------- 용어 사전 ----------
with tab_dict:
    with st.container(border=True):
        st.markdown("**오늘의 용어**")
        glossary.card(glossary.today_term())

    c1, c2 = st.columns([2, 3])
    with c1:
        q = st.text_input("검색", placeholder="PER, 환율, 신용스프레드", key="tq")
    with c2:
        cats = st.pills("분류", glossary.CATEGORIES, selection_mode="multi", key="tc")

    shown = [
        t for t in terms
        if (not cats or t["category"] in cats)
        and (not q or q.lower() in (t["term"] + t.get("en", "") + t["short"]).lower())
    ]
    st.caption(f"{len(shown)}개 용어")
    if not shown:
        st.info("찾는 용어가 없어요. 다른 말로 검색해 보세요.")
    for cat in glossary.CATEGORIES:
        group = [t for t in shown if t["category"] == cat]
        if not group:
            continue
        st.markdown(f"#### {cat}")
        cols = st.columns(2)
        for i, t in enumerate(group):
            with cols[i % 2], st.expander(f"**{t['term']}** — {t['short']}"):
                glossary.card(t, show_related=True)

# ---------- 퀴즈 ----------
with tab_quiz:
    st.caption("설명을 보고 맞는 용어를 골라요. 틀린 문제는 설명이 바로 나와요.")
    ss = st.session_state
    pool_cats = st.pills("문제 범위", glossary.CATEGORIES, selection_mode="multi",
                         default=glossary.CATEGORIES, key="quiz_cats")
    pool = [t for t in terms if t["category"] in (pool_cats or glossary.CATEGORIES)]

    def new_question() -> None:
        ans = random.choice(pool)
        others = random.sample([t for t in pool if t["term"] != ans["term"]], k=min(3, len(pool) - 1))
        opts = [ans["term"]] + [t["term"] for t in others]
        random.shuffle(opts)
        ss.quiz = {"answer": ans["term"], "options": opts, "picked": None}

    if "quiz" not in ss or ss.quiz["answer"] not in [t["term"] for t in pool]:
        if len(pool) >= 2:
            new_question()
        ss.setdefault("score", [0, 0])

    if len(pool) < 2:
        st.info("문제 범위를 하나 이상 골라 주세요.")
    else:
        quiz = ss.quiz
        ans = glossary.get(quiz["answer"])
        st.markdown(f"#### {ans['short']}")
        if ans.get("detail"):
            st.caption(ans["detail"])

        if quiz["picked"] is None:
            cols = st.columns(2)
            for i, o in enumerate(quiz["options"]):
                if cols[i % 2].button(o, key=f"opt_{o}", width="stretch"):
                    quiz["picked"] = o
                    ss.score[1] += 1
                    if o == quiz["answer"]:
                        ss.score[0] += 1
                    st.rerun()
        else:
            if quiz["picked"] == quiz["answer"]:
                st.success(f"맞았어요. 정답은 **{quiz['answer']}**예요.")
            else:
                st.error(f"아쉬워요. 고른 답은 {quiz['picked']}, 정답은 **{quiz['answer']}**예요.")
                with st.container(border=True):
                    glossary.card(ans)
            if st.button("다음 문제", type="primary"):
                new_question()
                st.rerun()

        right, total = ss.score
        st.caption(f"지금까지 {total}문제 중 {right}문제 맞혔어요.")

st.divider()
ui.disclaimer()
