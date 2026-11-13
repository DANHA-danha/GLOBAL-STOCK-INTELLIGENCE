# 주식랩 (가칭)

미국 정책 → 한국 경제 → 산업 → 기업 → 과거 주가로 이어지는 흐름을 데이터로 공부하는 주식·경제 분석 웹이에요.
지금은 **3단계**까지 만들었어요.

| 화면 | 하는 일 |
|---|---|
| 홈 | 오늘의 숫자 4개, 지금 숫자가 말하는 것(연결 고리), 다가오는 일정, 오늘의 용어 |
| 경제 상황판 | 한국·미국·유로존·일본·중국의 금리·물가·환율, 한미 금리차, 미국 장단기 금리차, 연결 고리 설명 |
| 기업 페이지 | 회사 개요, 현재 주가·52주 최고/최저·시가총액, PER·PBR·ROE·영업이익률·부채비율·배당수익률, 주가 1~10년(최대 낙폭 표시, 지수 비교), 연도별 수익률, 최근 6년 실적 |
| 모의투자 | 과거 날짜에 한 번에 투자하거나 매달 적립했다면 지금 얼마인지. 최대 3종목 비교, 연평균 수익률·최대 낙폭·코스피(S&P 500) 대비, 미국 종목은 환율까지 반영 |
| 금리 결정 전후 | 미국이 기준금리를 내리거나 올렸던 날들을 모아, 발표 전후 코스피·종목이 평균적으로 어떻게 움직였는지(이벤트 스터디). 사이클의 첫 결정만 따로 볼 수 있어요 |
| 산업 지도 | 금리·환율·유가·AI 투자·관세 등 경제 변화 → 유리/불리해질 수 있는 산업 → 관심 종목. 지금 지표로 해당되는 변화를 자동 표시 |
| 일정 캘린더 | FOMC·금통위 금리 결정일, 미국 CPI·고용·GDP 발표일과 D-day |
| 용어 튜터 | 60개 용어(뜻·계산식·예시·주의할 점), 검색, 분류, 퀴즈. 다른 화면의 물음표 버튼으로도 열려요 |

## 처음 실행하기

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

브라우저에서 `http://localhost:8501`이 열려요. 용어 튜터와 일정 캘린더는 바로 쓸 수 있고, 경제 지표는 아래 '데이터 받기'를 해야 채워져요.

## 데이터 받기

> Mac에서는 아래 명령어의 `python`을 모두 `python3`로 바꿔서 입력하세요.

무료 API 키 세 개가 필요해요.

1. **한국은행 ECOS**: [ecos.bok.or.kr](https://ecos.bok.or.kr/api/) → 회원가입 → 인증키 신청
2. **미국 FRED**: [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html) → 계정 만들기 → API Key 요청 (바로 나와요)
3. **Open DART**: [opendart.fss.or.kr](https://opendart.fss.or.kr) → 인증키 신청 (한국 종목 재무제표용)

`.env.example`을 복사해 `.env`로 이름을 바꾸고 키를 넣은 뒤 실행해요.

```bash
python scripts/collect.py          # 경제 지표
python scripts/collect_stocks.py   # 종목 주가·재무 (주가는 키 없이도 받아요)
```

결과에 성공·건너뜀·실패 목록이 나와요. 받은 값은 `data/series/*.csv`에 저장되고, 앱은 이 파일만 읽어요.
실패한 지표가 있으면 `config/series.yaml`에서 그 지표의 코드(ECOS는 `stat`·`item`, FRED는 `id`)를 확인해 고치면 돼요.

## 매일 자동으로 받기 (GitHub Actions)

`.github/workflows/collect.yml`이 매일 아침 7시 17분(한국 시간)에 지표를 받아 `data/`를 커밋해요.

1. GitHub 저장소 → Settings → Secrets and variables → Actions → New repository secret
2. `ECOS_API_KEY`, `FRED_API_KEY`, `DART_API_KEY` 세 개를 넣어요
3. Actions 탭 → collect → Run workflow로 한 번 직접 돌려 확인해요

`.env`는 `.gitignore`에 들어 있어서 Git에 올라가지 않아요. 키는 꼭 Secrets에만 넣으세요.

## 폴더 구조

```
app.py                  메뉴(상단 탭)와 페이지 연결
views/                  화면 하나당 파일 하나
  home.py  economy.py  company.py  simulator.py  events.py  industry.py  calendar.py  tutor.py
lib/
  data.py               data/ 파일 읽기, 최신값·변화 계산
  insights.py           연결 고리 규칙 (한미 금리차, 장단기 금리차, 달러·원화·엔화, 물가)
  stocks.py             종목 데이터 읽기, 투자 지표·연도별 수익률·모의투자 계산
  events.py             미국 기준금리 변경일 찾기, 발표 전후 주가 경로 계산
  industry.py           산업 지도 읽기, 지금 해당되는 변화(금리·환율·유가) 판단
  glossary.py           용어 사전, 어디서든 term("PER")로 물음표 버튼
  ui.py                 지표 카드, 차트, 일정 줄, 안내 문구
config/series.yaml      보여줄 지표 목록과 API 코드
config/universe.yaml    기업 페이지·모의투자에서 고를 종목과 비교 지수
config/industry_map.yaml  경제 변화 → 산업 → 종목 연결 (직접 고치고 늘릴 수 있어요)
data/
  glossary.yaml         용어 55개 (여기에 추가하면 바로 반영)
  events.yaml           FOMC·금통위 일정 (직접 관리)
  series/               collect.py가 만든 지표 CSV
  events_auto.csv       collect.py가 받은 미국 지표 발표일
  stocks/<종목코드>/      prices.csv(주가), financials.csv(재무), info.json(개요)
scripts/collect.py      ECOS·FRED 수집
scripts/collect_stocks.py  주가(Yahoo Finance)·재무(Open DART) 수집
```

## 고치고 늘리는 법

- **용어 추가**: `data/glossary.yaml` 맨 아래에 같은 형식으로 추가해요. `category`는 기본, 기업 분석, 경제 지표, 채권·자본시장, 투자·수급, 시장 중 하나예요.
- **지표 추가**: `config/series.yaml`에 넣고 `python scripts/collect.py`를 다시 실행해요.
- **연결 고리 규칙 추가**: `lib/insights.py`의 `build()`에 규칙을 하나 더 쓰면 홈과 경제 상황판에 같이 나와요.
- **종목 추가**: `config/universe.yaml`에 한 줄 넣고 `python scripts/collect_stocks.py`를 실행해요.
- **일정 추가**: `data/events.yaml`에 한 줄 추가해요. 2027년 FOMC 일정은 직전 회의에서 확정되니 가끔 [연준 일정](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm)과 비교해 주세요.

## 다음 단계

- [x] 2단계: 기업 페이지(Open DART 재무제표 + 과거 주가) + 모의투자(CAGR, MDD, 코스피 대비)
- [ ] 미국 종목 재무제표(SEC EDGAR)
- [x] 3단계: 이벤트 스터디(금리 결정 전후) + 경제 변화 → 산업 → 종목 연결
- [ ] 한국은행 금리 결정 전후 (기준금리 일별 데이터 필요)
- [ ] 4단계: AI 뉴스 분석·기업 리포트 + 조건 검색 + 투자 일지
- [ ] 5단계: 백테스트 + 자본시장 메뉴(회사채·신용스프레드·IPO)
- [ ] 중국 제조업 PMI (무료 API 찾기)

## 주의

주가는 Yahoo Finance에서 받아요. 개인 공부용으로는 괜찮지만, 사이트를 공개할 때는 데이터 제공처 약관을 확인해야 해요.

설명과 연결 고리는 공부를 위한 참고 자료이고, 특정 종목이나 상품의 투자를 권유하지 않아요. 지표 하나로 주가가 정해지지 않아서 문장을 모두 "~할 수 있어요"로 썼어요.
