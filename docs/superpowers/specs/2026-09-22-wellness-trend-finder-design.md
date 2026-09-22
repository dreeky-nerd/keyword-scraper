# 주간 웰니스 트렌드 파인더 — 설계 문서

작성일: 2026-09-22
상태: 승인 (2026-09-22)

## 1. 목적

한국 소재 사우나 사업장의 **팝업·비치 물건 소싱 의사결정**을 위해, 매주 1회 "이번 주 핫한 웰니스 제품 또는 행위"를 키워드 입력 없이 **발견**하고, 근거와 함께 상위 10개를 리포트한다.

- 모드: 발견(B). 키워드 → 점수 측정(A) 아님
- 도메인: 웰니스 전체. 사우나 용품 한정 아님
- 대상: 제품(product) + 행위(behavior). 예: 마그네슘 글리시네이트, 레드라이트 마스크 / mouth taping, cold plunge, fibermaxxing
- 지역: 2트랙 — 글로벌(EN) seed = 선행지표, KR 트랙 = 국내 현재 상태
- 경쟁사(Othership, 사우나스, Bathclub) 모니터링은 **하지 않음** — 그들이 들여온 것은 이미 늦음

## 2. "핫함" 정의와 정량화

핫함 = 절대 언급량이 아니라 **기준선 대비 급등(velocity)**.

| 기준 | 정량 지표 | v1 소스 |
|---|---|---|
| 1. 대중성·화제성 | 검색 관심도 상승률, 해시태그 게시물 증가율 | Google Trends, TikTok CC, Instagram, Naver DataLab |
| 2. 희소성·대기 | 리셀 프리미엄, 품절률 | v2 (Kream, Amazon) |
| 3. 모방·확산 | UGC 증가율, 고유 작성자 수 / 게시물 수 | TikTok CC, Instagram |
| 4. 자발적 바이럴 | organic 비율 (비브랜드 계정 게시물 / 전체) | Instagram |
| 5. 자본·기업 움직임 | 콜라보·팝업 기사 수 | v2 (GDELT, Popply) |

정규화: 지표별 `z = (현재 − 기준선 평균) / 기준선 표준편차`. 기준선 = 자체 DB의 직전 4~8주 (초기 주차는 소스 자체 상대지표 사용).

합성 점수:
```
hot_score = Σ w_i · z_i          (결측 소스 가중치는 나머지에 비례 재분배)
w: 검색·언급 속도 0.35, UGC 확산 0.25, organic 비율 0.15, 다소스 교차 0.25
```
행위(behavior)는 기준 2·5 해당 없음 — 재분배 규칙으로 자동 처리.

**다소스 교차**: 검증 fan-out까지 마친 뒤 v1 소스 5개 중 3개 이상에서 유의미한 신호(z ≥ 1 또는 소스 자체 상승 지표) = 1차 필터 통과 조건. 1~2개 소스만 등장한 후보는 `WATCHING` 라벨로 저장만 하고 리포트 제외. seed 소스(TikTok CC, Google Trends, Reddit) 1개에만 떠도 검증 fan-out은 수행.

## 3. 생애주기 라벨

주차 시계열 기반. 분석팀 팀장이 판정.

| 라벨 | 조건 |
|---|---|
| `NEW` | 이번 주 처음 등장 + z ≥ 2 |
| `RISING` | 2주 이상 연속 상승 |
| `PEAK` | 상승 멈춤, 직전 주 대비 ±10% |
| `DECLINING` | 2주 연속 하락 |
| `WATCHING` | 교차 소스 < 3 |

글로벌-KR 갭 라벨 (리포트에 병기):
- `GLOBAL_ONLY` — 글로벌 급등, KR 미도달 → 팝업 선점 후보
- `KR_HOT` — 국내 급등 → 지금 비치
- `KR_PAST_PEAK` — 국내 정점 지남 → 제외 권고

## 4. 아키텍처

```
[스케줄러 — 주 1회]
      │
[오케스트레이터 — 코드, 결정적]
      │
      ├─ 1. 자료조사팀 ──▶ raw_signals
      │       └ 비판자 PASS/REVISE/REJECT
      ├─ 2. 정제팀 ──────▶ candidates
      │       └ 비판자
      ├─ 3. 분석팀 ──────▶ scored_candidates
      │       └ 비판자
      └─ 4. 리포트팀 ────▶ weekly_report.md
              └ 비판자
      │
[SQLite — 주차 시계열 · 후보 · 리포트 이력]
```

- 팀 = LLM 에이전트 그룹. 팀 간 전달은 pydantic 스키마로 고정
- 오케스트레이터는 LLM 아님. 순서 실행, 재작업 1회 제한, 실패 소스 skip, 비용 로깅
- 숫자 계산(z-score, 증가율)은 코드. LLM은 추출·판단·해석만

## 5. 팀 구성 (총 19명)

모델 비율: Fable 2명 제외 17명 = Sonnet 12 : Opus 5 (≈ 7:3). 비판자 4명 전원 Opus.

### 5.1 자료조사팀 (5)
| 역할 | 모델 | 도구 |
|---|---|---|
| SNS 수집 | Sonnet | TikTok Creative Center(playwright), Apify Instagram |
| 검색 수집 | Sonnet | Google Trends(pytrends 또는 Apify 액터) |
| 커뮤니티 수집 | Sonnet | Reddit(praw) |
| KR 수집 | Sonnet | Naver DataLab API, Apify Instagram(한글 해시태그) |
| 비판자 | Opus | — |

비판 기준: 소스 실패·결측, 데이터 신선도(7일 초과), 단일 소스 편중, 봇·광고 게시물 비율.

### 5.2 정제팀 (4)
| 역할 | 모델 |
|---|---|
| 개체 추출 | Sonnet |
| 병합·정규화 (다국어 동일 개체 판단) | Opus |
| 웰니스 게이트·제품/행위·하위카테고리 태깅 | Sonnet |
| 비판자 | Opus |

병합 전 `rapidfuzz`로 후보 쌍 좁힌 뒤 LLM 판단. 하위카테고리: 수면 / 영양·보충제 / 스킨케어 / 운동·회복 / 멘탈·호흡 / 향·사운드 / 기타.
비판 기준: 오병합(다른 것 합침), 미병합(같은 것 둘), 비웰니스 통과, 브랜드명 vs 일반명사 혼동.

### 5.3 분석팀 (5)
| 역할 | 모델 |
|---|---|
| **팀장** — 지표 종합, hot_score·생애주기·갭 라벨 최종 판정 | **Fable** |
| 속도·z-score 해석 | Sonnet |
| 계절성·과거 주차 비교 | Sonnet |
| 글로벌-KR 갭 분석 | Sonnet |
| 비판자 | Opus |

비판 기준: 단일 소스 스파이크, 광고 캠페인 인위 급등, 계절성(매년 반복), 뉴스 1건 스파이크, 이미 정점 지남. 감점·제외 요구 가능.

### 5.4 리포트(선정)팀 (5)
| 역할 | 모델 |
|---|---|
| **팀장** — 상위 10 선정, 팝업/비치 구현 형태 판단 | **Fable** |
| 후보 카드 작성 | Sonnet |
| 브랜드·근거 링크 검증 (HEAD 요청) | Sonnet |
| 참조 링크 탐색·검증 — 브랜드 공식, 구매 페이지(글로벌·KR), 설명 기사, 행위면 how-to | Sonnet |
| 비판자 | Opus |

참조 링크 탐색은 Claude `web_search` 서버 툴 사용 (`allowed_domains` 없이, `max_uses` 5/후보). 링크는 HEAD 200 확인 후 채택.
비판 기준: 근거 링크 유효, 참조 링크 유효·종류별 최소 1개(제품: brand_official 또는 product_page / 행위: explainer 또는 how_to), 브랜드 연락 가능성, 수입 가능성, 리스트 길이(10개 초과 불허).

## 6. 비판자 프로토콜 (공통)

- 출력 고정: `{"verdict": "PASS" | "REVISE" | "REJECT", "issues": [...]}`
- `REVISE`: 해당 팀 재작업 **최대 1회**. 2차도 REVISE면 `warnings`에 사유 붙여 다음 팀으로 진행
- `REJECT`: 해당 주차 파이프라인 중단, 사유 로그. (조사팀 REJECT = 수집 신뢰 불가)
- 비판자는 자기 팀 산출물만 본다

## 7. 데이터 계약 (pydantic)

```python
class RawSignal(BaseModel):
    source: Literal["tiktok_cc", "google_trends", "reddit", "instagram", "naver_datalab"]
    region: Literal["global", "kr"]
    term: str                     # 원문 그대로
    metric_name: str              # "hashtag_views_7d", "rising_pct", ...
    metric_value: float
    collected_at: datetime
    url: str | None
    raw: dict                     # 원천 payload

class Candidate(BaseModel):
    canonical_name: str           # 영문 정규명
    aliases: list[str]            # 다국어 별칭
    kind: Literal["product", "behavior"]
    subcategory: str
    is_wellness: bool
    signals: list[RawSignal]
    source_count: int

class ScoredCandidate(Candidate):
    hot_score: float
    z_scores: dict[str, float]
    lifecycle: Literal["NEW","RISING","PEAK","DECLINING","WATCHING"]
    gap_label: Literal["GLOBAL_ONLY","KR_HOT","KR_PAST_PEAK","UNKNOWN"]
    analyst_notes: str
    warnings: list[str]

class ReferenceLink(BaseModel):
    kind: Literal["brand_official", "product_page", "explainer", "how_to"]
    url: str
    title: str
    region: Literal["global", "kr"]

class ReportCard(BaseModel):
    candidate: ScoredCandidate
    rank: int
    popup_form: str               # "팝업 부스 / 리테일 비치 / 클래스·이벤트"
    brands: list[str]
    evidence_urls: list[str]      # 왜 핫한가 — 신호 원문(TikTok·Reddit·Trends). 검증 통과한 것만
    reference_urls: list[ReferenceLink]  # 그게 뭔가 — 브랜드 공식·구매 페이지·설명 기사. 검증 통과한 것만
    one_liner: str


class CriticVerdict(BaseModel):
    verdict: Literal["PASS","REVISE","REJECT"]
    issues: list[str]
```

LLM 호출은 `client.messages.parse()` + 위 스키마로 구조화 출력.

## 8. 소스별 수집 상세 (v1)

| 소스 | 방법 | 수집 내용 | 주기 한계 |
|---|---|---|---|
| TikTok Creative Center | playwright 스크랩 | industry=Health/Beauty/Sports 해시태그 트렌드, 7일 필터 | 공식 API 없음, DOM 변경 리스크 |
| Google Trends | pytrends (fallback: Apify 액터) | category=Health(45) rising queries, geo=US/GB/KR | rate limit 심함 |
| Reddit | praw | r/Supplements r/Biohackers r/longevity r/SkincareAddiction r/sleep r/Fitness 주간 top 100 | 무료 |
| Instagram | Apify `instagram-hashtag-scraper`, `instagram-search-scraper` | 정제팀 후보 해시태그 → 게시물 수·최근 게시물·작성자 팔로워 | $2.3/1k, 후보 있어야 동작 → **검증 단계에서 호출** |
| Naver DataLab | 공식 REST API | 후보 키워드 검색 트렌드, 쇼핑인사이트 | 키워드 입력 필요 → 검증 단계 |

Instagram·Naver는 seed가 아니라 **정제 후 검증 fan-out**. 오케스트레이터가 정제팀 산출 후 조사팀을 2차 호출.

v2 후보: Amazon Movers & Shakers, GDELT, YouTube, Popply, Kream.

## 9. 저장

SQLite 단일 파일. 테이블:
- `runs` (run_id, week, started_at, status, cost_usd)
- `raw_signals` (run_id, ...RawSignal)
- `candidates` (run_id, canonical_name, ...) — 주차별 스냅샷
- `candidate_history` (canonical_name, week, hot_score, lifecycle) — 시계열
- `reports` (run_id, markdown)
- `critic_logs` (run_id, team, verdict, issues, attempt)

## 10. 출력

`reports/YYYY-WW.md`. 카드 형식:

```
## 3. Mouth Taping  [behavior · 수면]  GLOBAL_ONLY · NEW
hot_score 4.2 | TikTok +310% (7d) | Reddit 12 posts | Google Trends breakout
KR: Naver 검색 미미
팝업 형태: 수면 클래스 + 테이프 제품 리테일
브랜드: Hostage Tape, Dream Recovery
근거: [tiktok](...) [reddit](...) [trends](...)
참조: [Hostage Tape 공식](...) [Amazon 제품](...) [설명 기사](...) [KR 구매처 없음]
경고: 단일 크리에이터 발 가능성 (분석 비판자)
```

## 11. 오류 처리

- 소스 수집 실패: 해당 소스 skip, `warnings` 기록, 나머지로 진행. 3개 이상 실패 시 조사팀 비판자가 REJECT
- LLM 호출: SDK 재시도(429/5xx) 기본 2회. `refusal` stop_reason 시 클라이언트가 같은 요청을 `claude-opus-5`로 1회 재호출 (parse 경로 통일 위해 서버측 `fallbacks` 미사용)
- 구조화 출력 파싱 실패: 1회 재호출, 재실패 시 해당 항목 drop + 로그
- 비용 상한: run당 $30 초과 시 중단 (usage 누적 감시)

## 12. 테스트

- 단위: 수집기별 파서(고정 fixture), z-score 계산, 생애주기 판정 규칙, 가중치 재분배
- 계약: 각 팀 출력이 pydantic 스키마 통과
- 통합: fixture 기반 1주차 end-to-end (LLM 호출은 녹화된 응답으로 대체)
- LLM 품질: 정제팀 병합 정답셋 20쌍, 게이트 정답셋 30개로 회귀 체크

## 13. 비용 추정

| 항목 | 월 |
|---|---|
| Apify | $49 |
| Claude API (주 1회 × 4, 후보 50~100개) | $20~60 |
| Naver DataLab, Reddit, YouTube | 무료 |
| 합계 | 약 $70~110 |

첫 3회 실행 `usage` 로그로 재산정.

## 14. 리스크·미결

- TikTok CC·pytrends 비공식 — 깨지면 Apify 액터로 교체 (인터페이스 동일하게 설계)
- 초기 4주 기준선 없음 — 소스 자체 상대지표(TikTok 7일 증가율, Trends rising %)로 대체
- 개체 모호성("crocs" 브랜드 vs 특정 제품) — 정제팀 비판자 + 정답셋으로 관리
- 리포트 전달 채널(Slack/Notion) 미결 — v1은 Markdown 파일

## 15. 구현 순서 (계획 문서에서 상세화)

1. 스키마 + SQLite + 오케스트레이터 골격 (LLM 없이 fixture로 흐름)
2. 자료조사팀 수집기 5개 + 비판자
3. 정제팀
4. 분석팀 (계산 코드 → Fable 판정)
5. 리포트팀
6. 스케줄러 + 비용 로깅
