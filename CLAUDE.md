# AI Newsletter System

AI 뉴스/논문 자동 크롤링 및 큐레이션 시스템

## 프로젝트 개요

이 프로젝트는 다양한 AI 관련 소스에서 최신 뉴스와 논문을 자동으로 수집하고, LLM을 활용하여 가장 중요한 기사를 선별하는 시스템입니다.

### 주요 기능

1. **자동 크롤링**: 4개 주요 AI 소스에서 최신 기사 수집
2. **Description 추출**: 각 기사의 본문에서 introduction 자동 추출 (병렬 처리)
3. **AI 큐레이션**: LLM을 활용한 지능형 기사 선별
4. **카테고리 분류**: Academic / Tech News 자동 분류
5. **뉴스레터 생성**: 큐레이션된 기사를 전문적인 plain text 이메일 뉴스레터로 자동 작성

---

## 시스템 아키텍처

```
┌─────────────┐
│  crawler.py │  ← 4개 소스 크롤링 + description 추출 (병렬)
└──────┬──────┘
       │
       ▼
┌──────────────────────────────┐
│ data/crawled_data/*.json     │  ← 크롤링 결과
└──────┬───────────────────────┘
       │
       ▼
┌─────────────┐
│ curator.py  │  ← LLM 큐레이션 (gpt-5-mini)
└──────┬──────┘
       │
       ▼
┌──────────────────────────────┐
│ data/curated/*.json          │  ← 큐레이션 결과
└──────┬───────────────────────┘
       │
       ▼
┌──────────────┐
│ news_writer.py│  ← 뉴스레터 생성 (gpt-5-mini)
└──────┬────────┘
       │
       ▼
┌──────────────────────────────┐
│ data/newsletters/*.txt       │  ← 최종 뉴스레터 (plain text)
└──────────────────────────────┘
```

---

## 파일 구조

```
AI-Newsletter/
├── crawler.py                      # 메인 크롤러
├── curator.py                      # LLM 큐레이터
├── news_writer.py                  # 뉴스레터 작성기
├── pipeline.py                     # 전체 파이프라인 실행
├── models.py                       # Pydantic 모델
├── requirements.txt                # 의존성
├── prompts/
│   ├── academic_curator.md         # Academic 큐레이션 프롬프트
│   ├── technews_curator.md         # Tech News 큐레이션 프롬프트
│   └── newsletter_writer.md        # Newsletter 작성 프롬프트
└── data/
    ├── crawled_data/               # 크롤링 결과
    │   └── crawler_results_YYMMDD_HHMM.json
    ├── curated/                    # 큐레이션 결과
    │   └── curated_YYMMDD_HHMM.json
    ├── newsletters/                # 뉴스레터
    │   ├── newsletter_YYMMDD_HHMM.json
    │   └── newsletter_YYMMDD_HHMM.txt
    └── articles/                   # 개별 기사 마크다운 (테스트용)
```

---

## 크롤링 소스

### Academic (학술)
- **alphaxiv** ([alphaxiv.org](https://www.alphaxiv.org))
  - arXiv 논문의 큐레이션 및 요약
  - Description: 목록 페이지에서 직접 수집 (별도 추출 불필요)

- **hf_blog** ([Hugging Face Blog](https://huggingface.co/blog))
  - Hugging Face 공식 블로그
  - Description: 첫 헤더 다음 ~ 두 번째 헤더 이전 또는 첫 이중개행까지

### Tech News (기술 뉴스)
- **venturebeat** ([venturebeat.com](https://venturebeat.com/category/ai/))
  - AI 산업 뉴스
  - Description: 첫 헤더 전 또는 헤더 다음부터 추출

- **ai_times** ([aitimes.com](https://www.aitimes.com))
  - 국내 AI 뉴스 (한국어)
  - Description: 첫 이중개행 이전까지

---

## Description 추출 로직

각 소스별로 본문에서 introduction을 자동 추출합니다:

1. **alphaxiv**: 목록 페이지에서 이미 description 제공 → 별도 추출 불필요
2. **나머지 소스**: 비동기 병렬로 각 URL 접속
   - 헤더 이전에 20자 이상 텍스트 → 사용
   - 헤더가 첫 줄 → 헤더 다음 ~ 두 번째 헤더 또는 첫 이중개행
   - 헤더 없음 → 첫 이중개행 이전
   - Fallback → 첫 500자

---

## LLM 큐레이션

### 모델: gpt-5-mini

⚠️ **특수 파라미터 사용:**
```python
llm = ChatOpenAI(
    model="gpt-5-mini",
    model_kwargs={
        "reasoning_effort": "medium",  # low, medium, high
        "max_completion_tokens": 2000
    }
)
```

**주의:** `temperature`, `max_tokens`는 사용 불가

### 카테고리별 선별 기준

#### Academic
- **필수 포함**: LLM 연구, Agent 시스템, NLP, RAG
- **포함 가능**: 멀티모달 (VLM, Audio-LLM)
- **제외**: 순수 이미지/영상 생성, Robotics

#### Tech News
- **필수 포함**: LLM 제품/서비스, 개발자 도구, Enterprise AI
- **포함 가능**: 멀티모달 제품, AI 비즈니스
- **제외**: 순수 이미지/영상 도구, Robotics 제품

각 카테고리에서 **1~3개** 기사 선별

---

## 출력 형식

### 크롤링 결과 (`data/crawled_data/crawler_results_*.json`)
```json
[
  {
    "source": "alphaxiv",
    "url": "https://www.alphaxiv.org",
    "timestamp": "2026-01-31T16:00:00",
    "articles_count": 20,
    "articles": [
      {
        "title": "...",
        "url": "https://...",
        "date": "2026-01-31",
        "description": "..."
      }
    ]
  }
]
```

### 큐레이션 결과 (`data/curated/curated_*.json`)
```json
{
  "timestamp": "2026-01-31T16:00:00",
  "academic": {
    "category": "academic",
    "selected_articles": [
      {
        "source": "alphaxiv",
        "title": "...",
        "url": "https://...",
        "description": "...",
        "reason_for_selection": "... (영어 2-3문장)"
      }
    ]
  },
  "technews": {
    "category": "technews",
    "selected_articles": [...]
  }
}
```

### 뉴스레터 결과 (`data/newsletters/newsletter_*.txt`)
Plain text 이메일 형식으로 생성:
```
Hello — welcome to this edition of the AI digest...

======================================================================

ACADEMIC RESEARCH

The academic section highlights recent papers...

1. [Article Title]

[4-5 sentence summary in professional tone]

Read more: https://...
Source: alphaxiv

----------------------------------------------------------------------

TECH NEWS

The tech news section covers recent product developments...

[Articles formatted similarly]

======================================================================

Thanks for reading...
```

---

## 설치 및 실행

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

**주요 패키지:**
- `trafilatura` - 웹 콘텐츠 추출
- `aiohttp` - 비동기 HTTP 요청
- `langchain` + `langchain-openai` - LLM 큐레이션
- `playwright` - alphaxiv 크롤링용

### 2. 환경 변수 설정

`.env` 파일 생성:
```bash
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. 실행

#### 전체 파이프라인 (권장)
```bash
python pipeline.py
```

전체 파이프라인은 다음 단계를 자동으로 실행합니다:
1. **crawler.py**: 4개 소스에서 기사 크롤링 + description 추출
2. **curator.py**: LLM을 통한 기사 큐레이션 (1-3개 선별)
3. **news_writer.py**: 큐레이션된 기사로 뉴스레터 생성

#### 개별 실행
```bash
python crawler.py      # 크롤링만
python curator.py      # 큐레이팅만 (크롤링 결과 필요)
python news_writer.py  # 뉴스레터 생성만 (큐레이션 결과 필요)
```

---

## 기술 스택

- **Python 3.10+**
- **크롤링**:
  - `requests` - HTTP 요청
  - `lxml` - HTML 파싱
  - `trafilatura` - 콘텐츠 추출
  - `playwright` - 동적 페이지
  - `aiohttp` - 비동기 병렬 처리
- **LLM**:
  - `langchain` - LLM 프레임워크
  - `langchain-openai` - OpenAI 통합
  - `pydantic` - 구조화된 출력
- **기타**:
  - `python-dotenv` - 환경 변수 관리

---

## 주요 기능 상세

### 1. 병렬 Description 추출

alphaxiv를 제외한 모든 소스는 각 URL에 병렬로 접속하여 description을 추출합니다:

```python
async def enrich_articles_with_descriptions(articles: List[Dict], source: str):
    """최대 10개 동시 연결로 병렬 처리"""
    connector = aiohttp.TCPConnector(limit=10)
    async with aiohttp.ClientSession(connector=connector) as session:
        # 병렬로 모든 기사의 description 추출
        ...
```

### 2. 구조화된 LLM 출력

Pydantic 모델을 사용하여 타입 안전성 보장:

```python
class SelectedArticle(BaseModel):
    source: Literal["alphaxiv", "hf_blog", "venturebeat", "ai_times"]
    index: int
    title: str
    reason_for_selection: str

class CurationResult(BaseModel):
    category: Literal["academic", "technews"]
    selected_articles: List[SelectedArticle]
```

### 3. Index 기반 Enrichment

LLM은 index만 반환하고, 원본 데이터에서 url/description을 추출:

```python
def enrich_selected_articles(result, articles_by_source):
    """LLM이 선택한 index를 사용하여 url, description 추가"""
    ...
```

### 4. 뉴스레터 자동 생성

큐레이션된 기사를 전문적인 plain text 이메일 뉴스레터로 변환:

```python
class Newsletter(BaseModel):
    greeting: str
    academic_section_intro: str
    academic_articles: List[ArticleSummary]
    technews_section_intro: str
    technews_articles: List[ArticleSummary]
    closing: str
```

**특징**:
- **전문적/학술적 톤**: 객관적이고 기술적인 내용 중심
- **4-5문장 요약**: 기술 혁신, 의미, 실용적 응용 포함
- **Plain text 형식**: 마크다운 없이 순수 텍스트로 이메일 전송 가능
- **통합 구조**: Academic + Tech News를 하나의 뉴스레터로 통합

---

## 개발 히스토리

### v1.0 - 기본 크롤링
- 4개 소스 크롤링 구현
- alphaxiv만 description 수집

### v2.0 - Description 개선
- 비동기 병렬 처리로 모든 소스의 description 추출
- 소스별 맞춤형 추출 로직

### v3.0 - LLM 큐레이션
- LangChain + gpt-5-mini 통합
- 카테고리별 프롬프트 분리
- Index 기반 enrichment

### v3.1 - 파이프라인 자동화
- pipeline.py 추가
- 크롤링 → 큐레이팅 한 번에 실행

### v4.0 - 뉴스레터 자동 생성
- news_writer.py 추가
- 큐레이션된 기사를 전문적인 plain text 뉴스레터로 자동 변환
- Newsletter Pydantic 모델 추가 (ArticleSummary, Newsletter)
- 전문적/학술적 톤의 4-5문장 요약 생성
- Academic + Tech News 통합 이메일 형식
- 전체 파이프라인: 크롤링 → 큐레이팅 → 뉴스레터 생성

---

## 트러블슈팅

### hf_blog description이 비어있음
- **원인**: 첫 줄이 바로 헤더인 경우 "헤더 이전" 텍스트가 없음
- **해결**: extract_introduction 로직 개선 (첫 헤더 다음부터 두 번째 헤더까지 추출)

### gpt-5-mini API 에러
- **원인**: temperature, max_tokens 파라미터 사용
- **해결**: reasoning_effort, max_completion_tokens 사용

### 크롤링 속도 느림
- **원인**: 순차 처리
- **해결**: aiohttp로 비동기 병렬 처리 (최대 10개 동시 연결)

---

## 향후 개선 방향

- [ ] 크롤링 스케줄링 (cron, GitHub Actions)
- [ ] 결과를 이메일/Slack으로 전송
- [ ] 더 많은 소스 추가
- [ ] 큐레이션 품질 메트릭 추가
- [ ] 웹 UI 구축
