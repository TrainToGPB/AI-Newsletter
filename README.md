# AI Newsletter 📰

AI 뉴스/논문을 자동으로 크롤링, 큐레이션하여 뉴스레터를 생성하는 시스템입니다.

## 주요 기능 ✨

- **자동 크롤링**: 4개 주요 AI 소스에서 최신 기사 수집 (alphaxiv, hf_blog, venturebeat, ai_times)
- **AI 큐레이션**: gpt-5-mini로 가장 중요한 1-3개 기사 자동 선별
- **중복 방지**: 최근 2주간 발송된 기사 자동 필터링
- **뉴스레터 생성**: 병렬 처리로 고품질 요약 생성 (간결한 음슴체 스타일)
- **자동 실행**: 매일 아침 6시 자동 실행 (launchd/cron)

## 시스템 아키텍처 🏗️

```
┌─────────────┐
│  crawler.py │  ← 4개 소스 크롤링
└──────┬──────┘
       │
       ▼
┌──────────────────────────────┐
│ data/crawled_data/*.json     │  ← 크롤링 결과
└──────┬───────────────────────┘
       │
       ▼
┌─────────────┐
│ memory.py   │  ← 중복 체크 (최근 2주)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ curator.py  │  ← LLM 큐레이션 (1-3개 선별)
└──────┬──────┘
       │
       ▼
┌──────────────────────────────┐
│ data/curated/*.json          │  ← 큐레이션 결과
└──────┬───────────────────────┘
       │
       ▼
┌─────────────┐
│news_writer.py│ ← 뉴스레터 생성 (병렬 처리)
└──────┬──────┘
       │
       ▼
┌──────────────────────────────┐
│ data/newsletters/*.json/txt  │  ← 최종 뉴스레터
└──────────────────────────────┘
```

## 설치 방법 🚀

### 1. 리포지토리 클론

```bash
git clone https://github.com/YOUR_USERNAME/AI-Newsletter.git
cd AI-Newsletter
```

### 2. 가상환경 생성 및 활성화

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
playwright install chromium  # alphaxiv 크롤링용
```

### 4. 환경 변수 설정

```bash
# .env 파일 생성
cp .env.example .env

# API 키 설정
echo "OPENAI_API_KEY=sk-your-api-key-here" > .env
```

## 사용 방법 📖

### 전체 파이프라인 실행

```bash
python pipeline.py
```

이 명령어는 다음을 순차 실행합니다:
1. 크롤링 (crawler.py)
2. 큐레이션 (curator.py)
3. 뉴스레터 생성 (news_writer.py)

### 개별 모듈 실행

```bash
# 크롤링만
python crawler.py

# 큐레이팅만
python curator.py

# 뉴스레터 생성만
python news_writer.py
```

## 자동 실행 설정 ⏰

매일 아침 6시에 자동으로 뉴스레터를 생성하도록 설정할 수 있습니다.

상세한 설정 방법은 [SCHEDULE_SETUP.md](SCHEDULE_SETUP.md)를 참고하세요.

**빠른 설정 (macOS):**

```bash
# 1. launchd에 등록
cp com.ai-newsletter.daily.plist ~/Library/LaunchAgents/
chmod 644 ~/Library/LaunchAgents/com.ai-newsletter.daily.plist

# 2. 시작
launchctl load ~/Library/LaunchAgents/com.ai-newsletter.daily.plist

# 3. 테스트 (지금 바로 실행)
launchctl start com.ai-newsletter.daily
```

## 크롤링 소스 📰

### Academic (학술)
- **alphaxiv** ([alphaxiv.org](https://www.alphaxiv.org)): arXiv 논문 큐레이션
- **hf_blog** ([Hugging Face Blog](https://huggingface.co/blog)): Hugging Face 공식 블로그

### Tech News (기술 뉴스)
- **venturebeat** ([venturebeat.com](https://venturebeat.com/category/ai/)): AI 산업 뉴스
- **ai_times** ([aitimes.com](https://www.aitimes.com)): 국내 AI 뉴스

## 주요 기능 상세 🔍

### 1. 중복 방지 메모리 시스템

- 최근 2주간 발송된 기사의 URL을 자동 추적
- URL 정규화로 95% 이상의 중복 감지율
- 추가 파일 불필요 (newsletter JSON이 메모리 역할)

### 2. LLM 큐레이션

- **모델**: gpt-5-mini (reasoning_effort: medium)
- **선별 기준**:
  - Academic: LLM 연구, Agent 시스템, NLP, RAG
  - Tech News: LLM 제품/서비스, 개발자 도구, Enterprise AI
- **결과**: 카테고리당 1-3개 기사

### 3. 병렬 뉴스레터 생성

- ThreadPoolExecutor로 6개 기사 동시 처리
- 각 기사당 3-5개 bullet point (짧고 간결한 음슴체)
- 전체 마크다운 본문 기반 요약

## 파일 구조 📁

```
AI-Newsletter/
├── crawler.py                      # 크롤러
├── curator.py                      # 큐레이터
├── news_writer.py                  # 뉴스레터 생성기
├── memory.py                       # 중복 방지 메모리
├── models.py                       # Pydantic 모델
├── pipeline.py                     # 전체 파이프라인
├── run_newsletter.sh               # 자동 실행 스크립트
├── com.ai-newsletter.daily.plist   # launchd 설정
├── SCHEDULE_SETUP.md               # 자동 실행 가이드
├── prompts/                        # LLM 프롬프트
│   ├── academic_curator.md
│   ├── technews_curator.md
│   ├── article_summarizer.md
│   └── newsletter_structure.md
├── data/
│   ├── crawled_data/               # 크롤링 결과
│   ├── curated/                    # 큐레이션 결과
│   ├── newsletters/                # 최종 뉴스레터
│   └── articles/                   # 기사 마크다운
└── logs/                           # 실행 로그
```

## 출력 예시 📄

### 뉴스레터 샘플

```
안녕하세요. 이번 호는 에이전트 역량 강화와 모델 효율화, 그리고 실무 도구의 통합이 두드러진 흐름으로 준비했습니다.

====================

ACADEMIC RESEARCH

학술 섹션은 에이전트의 추론·보상 설계 개선, 사전학습 과정의 반복적 향상, 그리고 계산 자원 최적화를 통한 모델 효율성 제고라는 공통된 주제를 다룹니다.

1. Exploring Reasoning Reward Model for Agents

• Agent-RRM은 에이전트 궤적에 대해 <think>, <critique>, <score>의 구조화된 다면적 피드백을 생성하는 보상 모델임
• Reagent-U가 GAIA 43.7%, WebWalkerQA 46.2%, AIME24 60.0% 달성했고 Reagent-R은 Bamboogle에서 72.8%로 향상했음
• 코드·모델과 총 80만개 이상의 예시 포함한 4개 고품질 데이터셋을 공개하여 재현성·해석 가능성 및 디버깅 용이성에 기여함

Read more: https://www.alphaxiv.org/abs/2601.22154

----------
...
```

## 로그 확인 📊

```bash
# 실행 로그
tail -f logs/newsletter_*.log

# launchd 로그 (자동 실행 시)
tail -f logs/launchd.out.log
tail -f logs/launchd.err.log
```

## 트러블슈팅 🔧

### API 키 오류

```bash
# .env 파일 확인
cat .env

# API 키가 올바른지 확인
# OPENAI_API_KEY=sk-...
```

### 가상환경 활성화 실패

```bash
# 가상환경 경로 확인
ls -la .venv/

# 재생성
rm -rf .venv
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Playwright 오류

```bash
# Playwright 재설치
playwright install chromium
```

## 기술 스택 🛠️

- **Python 3.10+**
- **LLM**: OpenAI gpt-5-mini
- **프레임워크**: LangChain, Pydantic
- **크롤링**: requests, lxml, trafilatura, playwright, aiohttp
- **비동기**: asyncio, ThreadPoolExecutor

## 라이센스 📝

MIT License

## 기여 🤝

이슈와 PR을 환영합니다!

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

**Made with ❤️ and Claude Sonnet 4.5**
