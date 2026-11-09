"""지표를 보고 "그래서 무슨 뜻인지" 연결 고리를 만들어요.

AI가 아니라 정해진 규칙이에요. 그래서 왜 이런 문장이 나왔는지 항상 숫자로 확인할 수 있어요.
문장은 "~할 수 있어요"로 써요. 지표 하나로 주가가 정해지지 않기 때문이에요.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from lib import data


@dataclass
class Insight:
    title: str
    fact: str                      # 숫자로 확인되는 사실
    chain: list[str]               # 이어지는 경로
    terms: list[str] = field(default_factory=list)
    watch: str = ""                # 다음에 볼 것


def _v(key: str) -> float | None:
    lt = data.latest(key)
    return lt.value if lt else None


def build() -> list[Insight]:
    out: list[Insight] = []

    kr, us = _v("kr_base_rate"), _v("us_fed_upper")
    if kr is not None and us is not None:
        gap = kr - us
        if gap < 0:
            out.append(Insight(
                "미국 금리가 한국보다 높아요",
                f"한미 금리차 {gap:+.2f}%p (한국 {kr:.2f}% · 미국 상단 {us:.2f}%)",
                ["달러로 돈을 굴리는 게 더 유리", "원화 약세 압력", "수입 물가 상승 가능, 수출 기업은 원화 환산 매출 증가 가능"],
                ["한미 금리차", "환율"],
                "FOMC와 금통위 결정에서 금리차가 좁혀지는지 보세요.",
            ))
        else:
            out.append(Insight(
                "한국 금리가 미국보다 높거나 같아요",
                f"한미 금리차 {gap:+.2f}%p (한국 {kr:.2f}% · 미국 상단 {us:.2f}%)",
                ["원화로 돈을 굴리는 매력 상승", "원화 강세 쪽 압력", "외국인 자금 유입에 우호적일 수 있음"],
                ["한미 금리차", "환율"],
            ))

    y10, y2 = _v("us_10y"), _v("us_2y")
    if y10 is not None and y2 is not None:
        sp = y10 - y2
        if sp < 0:
            out.append(Insight(
                "미국 장단기 금리가 역전돼 있어요",
                f"10년 {y10:.2f}% − 2년 {y2:.2f}% = {sp:+.2f}%p",
                ["시장이 앞으로 금리 인하를 예상", "경기 둔화 우려 신호", "경기에 민감한 업종에 부담일 수 있음"],
                ["장단기 금리차", "경기침체"],
                "역전 뒤 실제 침체까지는 몇 달에서 2년 이상 걸렸어요. 실업률과 함께 보세요.",
            ))
        else:
            out.append(Insight(
                "미국 장단기 금리는 정상(플러스)이에요",
                f"10년 {y10:.2f}% − 2년 {y2:.2f}% = {sp:+.2f}%p",
                ["장기 금리가 단기보다 높은 보통 상태", "당장 침체를 예상하는 신호는 약함"],
                ["장단기 금리차"],
            ))

    d3 = data.change_over("us_dollar", 3)
    if d3 is not None and abs(d3) >= 1:
        up = d3 > 0
        out.append(Insight(
            "달러가 " + ("강해지고 있어요" if up else "약해지고 있어요"),
            f"달러지수 3개월 {d3:+.2f}",
            (["신흥국 통화 약세", "외국인이 한국 증시에서 돈을 뺄 유인", "대형주 수급에 부담일 수 있음"] if up
             else ["신흥국 통화 강세", "외국인 자금이 한국 증시로 들어올 유인", "대형주 수급에 우호적일 수 있음"]),
            ["달러지수", "외국인 순매수"],
        ))

    w3 = data.change_over("kr_usdkrw", 3)
    if w3 is not None and abs(w3) >= 20:
        up = w3 > 0
        out.append(Insight(
            "원화가 " + ("약해졌어요 (환율 상승)" if up else "강해졌어요 (환율 하락)"),
            f"원/달러 3개월 {w3:+,.0f}원",
            (["수출 기업은 같은 달러 매출을 원화로 더 많이 받음", "수입 원자재·에너지 비용 상승", "물가 부담 → 금리 인하가 어려워질 수 있음"] if up
             else ["수입 원자재 비용 부담 완화", "수출 기업의 원화 환산 이익은 줄 수 있음", "물가 안정에 도움"]),
            ["환율"],
        ))

    t3 = data.change_over("us_10y", 3)
    if t3 is not None and abs(t3) >= 0.3:
        up = t3 > 0
        out.append(Insight(
            "미국 장기 금리가 " + ("크게 올랐어요" if up else "크게 내렸어요"),
            f"미국 10년 국채금리 3개월 {t3:+.2f}%p",
            (["위험 없이 받는 이자 상승", "미래 이익을 보고 사는 성장주 가치에 부담", "대출금리도 따라 오를 수 있음"] if up
             else ["위험 없이 받는 이자 하락", "성장주 가치에 우호적", "대출금리 하락 여지"]),
            ["국채금리", "PER"],
        ))

    for key, name in (("us_cpi_yoy", "미국"), ("kr_cpi_yoy", "한국")):
        c = _v(key)
        if c is None:
            continue
        if c >= 2.5:
            out.append(Insight(
                f"{name} 물가가 목표(2%)보다 높아요",
                f"소비자물가 상승률 {c:.1f}%",
                ["중앙은행이 금리를 내리기 어려움", "금리 인하 기대가 늦춰질 수 있음"],
                ["CPI", "기준금리"],
            ))
        elif c <= 1.5:
            out.append(Insight(
                f"{name} 물가가 목표(2%)보다 낮아요",
                f"소비자물가 상승률 {c:.1f}%",
                ["금리를 내릴 여유가 생김", "다만 수요가 약하다는 신호일 수도 있음"],
                ["CPI", "기준금리"],
            ))

    j3 = data.change_over("jp_usdjpy", 3)
    if j3 is not None and abs(j3) >= 5:
        up = j3 > 0
        out.append(Insight(
            "엔화가 " + ("약해졌어요" if up else "강해졌어요"),
            f"엔/달러 3개월 {j3:+.1f}엔",
            (["일본 수출품 가격이 싸짐", "자동차·기계 등 일본과 경쟁하는 한국 수출 기업에 부담일 수 있음"] if up
             else ["일본 제품 가격 경쟁력 약화", "일본과 경쟁하는 한국 수출 기업에 숨통이 트일 수 있음"]),
            ["환율"],
        ))
    return out
