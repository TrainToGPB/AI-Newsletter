#!/usr/bin/env python3
"""
AI Newsletter Writer
큐레이션된 기사를 바탕으로 전문적인 뉴스레터를 생성합니다.
각 기사를 병렬로 처리하여 높은 품질의 요약을 생성합니다.
"""

import json
import os
import asyncio
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor

from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

from models import Newsletter, ArticleSummary


def load_prompt(path: str) -> str:
    """프롬프트 마크다운 파일 로드"""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def load_latest_curated_data() -> Dict[str, Any]:
    """
    data/curated/에서 가장 최근 큐레이션 결과 로드

    Returns:
        {
            "timestamp": "...",
            "academic": {...},
            "technews": {...}
        }
    """
    curated_data_dir = Path("data/curated")
    if not curated_data_dir.exists():
        raise FileNotFoundError(
            f"Curated data directory not found: {curated_data_dir}\n"
            "Please run curator.py first."
        )

    # 가장 최근 JSON 파일 찾기
    json_files = list(curated_data_dir.glob("curated_*.json"))
    if not json_files:
        raise FileNotFoundError(
            f"No curated results found in {curated_data_dir}\n"
            "Please run curator.py first."
        )

    latest_file = sorted(json_files)[-1]
    print(f"📂 Loading curated data: {latest_file}")

    with open(latest_file, 'r', encoding='utf-8') as f:
        curated_data = json.load(f)

    # 통계 출력
    academic_count = len(curated_data.get("academic", {}).get("selected_articles", []))
    technews_count = len(curated_data.get("technews", {}).get("selected_articles", []))
    print(f"  ✓ Academic articles: {academic_count}")
    print(f"  ✓ Tech News articles: {technews_count}")

    return curated_data


def url_to_hash(url: str) -> str:
    """URL을 짧은 hash로 변환 (8자)"""
    return hashlib.md5(url.encode()).hexdigest()[:8]


def load_article_markdown(article: Dict[str, Any]) -> str:
    """
    저장된 마크다운 파일에서 기사 본문 로드

    Args:
        article: {"source": "...", "url": "...", "title": "..."}

    Returns:
        마크다운 본문 (frontmatter 제외)
    """
    source = article.get('source', 'unknown')
    url = article.get('url', '')

    if not url:
        return ""

    # 파일 경로 생성
    file_hash = url_to_hash(url)
    markdown_file = Path(f"data/articles/{source}/{file_hash}.md")

    if not markdown_file.exists():
        print(f"  ⚠️  Markdown file not found: {markdown_file}")
        return ""

    # 파일 읽기
    with open(markdown_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # frontmatter 제거 (--- ... --- 부분)
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            content = parts[2].strip()

    return content


def summarize_article_sync(
    llm: ChatOpenAI,
    article: Dict[str, Any],
    prompt_template: str,
    article_idx: int,
    total: int
) -> ArticleSummary:
    """
    개별 기사를 요약 (동기 함수)

    Args:
        llm: ChatOpenAI 모델
        article: 기사 정보 {"source": "...", "url": "...", "title": "..."}
        prompt_template: 프롬프트 템플릿
        article_idx: 현재 기사 인덱스 (로깅용)
        total: 전체 기사 수 (로깅용)

    Returns:
        ArticleSummary 객체
    """
    title = article.get('title', 'Unknown')
    source = article.get('source', 'unknown')
    url = article.get('url', '')

    print(f"  [{article_idx}/{total}] Summarizing: {title[:50]}...")

    # 마크다운 본문 로드
    article_content = load_article_markdown(article)

    if not article_content:
        print(f"    ⚠️  No content found, using description as fallback")
        article_content = article.get('description', 'No content available')

    # 프롬프트 생성
    prompt = prompt_template.replace('{article_content}', article_content)

    # LLM with structured output
    structured_llm = llm.with_structured_output(ArticleSummary)

    # 요약 생성
    summary = structured_llm.invoke(prompt)

    # URL과 source 설정 (LLM이 제대로 반환하지 않을 수 있으므로)
    summary.url = url
    summary.source = source
    summary.title = title

    print(f"    ✓ Generated {len(summary.summary_points)} bullet points")

    return summary


async def summarize_articles_parallel(
    llm: ChatOpenAI,
    articles: List[Dict[str, Any]],
    prompt_template: str
) -> List[ArticleSummary]:
    """
    여러 기사를 병렬로 요약

    Args:
        llm: ChatOpenAI 모델
        articles: 기사 정보 리스트
        prompt_template: 프롬프트 템플릿

    Returns:
        ArticleSummary 객체 리스트
    """
    total = len(articles)
    print(f"\n🤖 Summarizing {total} articles in parallel...")

    # ThreadPoolExecutor를 사용한 병렬 처리
    with ThreadPoolExecutor(max_workers=6) as executor:
        loop = asyncio.get_event_loop()
        tasks = []
        for idx, article in enumerate(articles, 1):
            task = loop.run_in_executor(
                executor,
                summarize_article_sync,
                llm,
                article,
                prompt_template,
                idx,
                total
            )
            tasks.append(task)

        # 모든 작업 완료 대기
        summaries = await asyncio.gather(*tasks)

    print(f"✅ All {total} articles summarized")
    return summaries


def generate_newsletter_structure(
    llm: ChatOpenAI,
    prompt_template: str,
    academic_titles: List[str],
    technews_titles: List[str]
) -> Dict[str, str]:
    """
    뉴스레터 구조 생성 (greeting, intro, closing)

    Args:
        llm: ChatOpenAI 모델
        prompt_template: 프롬프트 템플릿
        academic_titles: Academic 기사 제목 리스트
        technews_titles: Tech News 기사 제목 리스트

    Returns:
        {"greeting": "...", "academic_section_intro": "...", ...}
    """
    print(f"\n📝 Generating newsletter structure...")

    # 제목 리스트를 텍스트로 변환
    academic_text = "\n".join([f"- {title}" for title in academic_titles])
    technews_text = "\n".join([f"- {title}" for title in technews_titles])

    # 프롬프트 생성
    prompt = prompt_template.replace('{academic_titles}', academic_text)
    prompt = prompt.replace('{technews_titles}', technews_text)

    # Pydantic 모델 정의
    from pydantic import BaseModel, Field

    class NewsletterStructure(BaseModel):
        greeting: str = Field(..., description="인사말 (1-2문장)")
        academic_section_intro: str = Field(..., description="Academic 섹션 소개 (1-2문장)")
        technews_section_intro: str = Field(..., description="Tech News 섹션 소개 (1-2문장)")
        closing: str = Field(..., description="마무리 인사 (1-2문장)")

    structured_llm = llm.with_structured_output(NewsletterStructure)
    structure = structured_llm.invoke(prompt)

    print(f"✅ Newsletter structure generated")

    return structure.model_dump()


def format_newsletter_text(newsletter: Newsletter) -> str:
    """
    Newsletter 객체를 plain text 이메일 형식으로 변환

    Args:
        newsletter: Newsletter Pydantic 모델

    Returns:
        Plain text 형식의 뉴스레터
    """
    lines = []

    # Greeting
    lines.append(newsletter.greeting)
    lines.append("")
    lines.append("=" * 20)
    lines.append("")

    # Academic Section
    lines.append("ACADEMIC RESEARCH")
    lines.append("")
    lines.append(newsletter.academic_section_intro)
    lines.append("")

    for idx, article in enumerate(newsletter.academic_articles, 1):
        lines.append(f"{idx}. {article.title}")
        lines.append("")
        # Bullet points
        for point in article.summary_points:
            lines.append(f"• {point}")
        lines.append("")
        lines.append(f"Read more: {article.url}")
        lines.append("")
        lines.append("-" * 10)
        lines.append("")

    # Tech News Section
    lines.append("TECH NEWS")
    lines.append("")
    lines.append(newsletter.technews_section_intro)
    lines.append("")

    for idx, article in enumerate(newsletter.technews_articles, 1):
        lines.append(f"{idx}. {article.title}")
        lines.append("")
        # Bullet points
        for point in article.summary_points:
            lines.append(f"• {point}")
        lines.append("")
        lines.append(f"Read more: {article.url}")
        lines.append("")
        lines.append("-" * 10)
        lines.append("")

    # Closing
    lines.append("=" * 20)
    lines.append("")
    lines.append(newsletter.closing)

    return "\n".join(lines)


async def generate_newsletter_async(
    llm: ChatOpenAI,
    article_prompt: str,
    structure_prompt: str,
    curated_data: Dict[str, Any]
) -> Newsletter:
    """
    뉴스레터 생성 (비동기)

    Args:
        llm: ChatOpenAI 모델
        article_prompt: 기사 요약 프롬프트
        structure_prompt: 뉴스레터 구조 프롬프트
        curated_data: 큐레이션 결과

    Returns:
        Newsletter 객체
    """
    academic_articles = curated_data.get("academic", {}).get("selected_articles", [])
    technews_articles = curated_data.get("technews", {}).get("selected_articles", [])

    all_articles = academic_articles + technews_articles

    # 1. 모든 기사를 병렬로 요약
    summaries = await summarize_articles_parallel(llm, all_articles, article_prompt)

    # 2. Academic과 Tech News로 분리
    academic_count = len(academic_articles)
    academic_summaries = summaries[:academic_count]
    technews_summaries = summaries[academic_count:]

    # 3. 뉴스레터 구조 생성
    academic_titles = [a.get('title', '') for a in academic_articles]
    technews_titles = [a.get('title', '') for a in technews_articles]

    structure = generate_newsletter_structure(
        llm, structure_prompt, academic_titles, technews_titles
    )

    # 4. Newsletter 객체 조합
    newsletter = Newsletter(
        greeting=structure['greeting'],
        academic_section_intro=structure['academic_section_intro'],
        academic_articles=academic_summaries,
        technews_section_intro=structure['technews_section_intro'],
        technews_articles=technews_summaries,
        closing=structure['closing']
    )

    return newsletter


def main():
    """메인 실행 함수"""
    # 환경 변수 로드
    load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError(
            "OPENAI_API_KEY not found in environment.\n"
            "Please create a .env file with: OPENAI_API_KEY=your_key_here"
        )

    print(f"\n{'='*60}")
    print("AI Newsletter Writer")
    print(f"{'='*60}\n")

    # 1. 큐레이션 데이터 로드
    curated_data = load_latest_curated_data()

    # 2. LLM 초기화 (gpt-5-mini)
    print(f"\n🔧 Initializing LLM (gpt-5-mini)...")
    llm = ChatOpenAI(
        model="gpt-5-mini",
        model_kwargs={
            "reasoning_effort": "medium",
            "max_completion_tokens": 3000
        }
    )
    print("   ✓ LLM initialized")

    # 3. 프롬프트 로드
    article_prompt = load_prompt("prompts/article_summarizer.md")
    structure_prompt = load_prompt("prompts/newsletter_structure.md")

    # 4. 뉴스레터 생성 (비동기)
    newsletter = asyncio.run(
        generate_newsletter_async(llm, article_prompt, structure_prompt, curated_data)
    )

    # 5. 결과 저장
    timestamp = datetime.now().strftime("%y%m%d_%H%M")
    output_dir = Path("data/newsletters")
    output_dir.mkdir(parents=True, exist_ok=True)

    # JSON 형식 저장
    json_output_file = output_dir / f"newsletter_{timestamp}.json"
    with open(json_output_file, 'w', encoding='utf-8') as f:
        json.dump(newsletter.model_dump(), f, ensure_ascii=False, indent=2)

    # Plain text 형식 저장
    text_output_file = output_dir / f"newsletter_{timestamp}.txt"
    newsletter_text = format_newsletter_text(newsletter)
    with open(text_output_file, 'w', encoding='utf-8') as f:
        f.write(newsletter_text)

    print(f"\n{'='*60}")
    print(f"✅ Newsletter Generation Complete!")
    print(f"{'='*60}")
    print(f"\n📄 Results saved:")
    print(f"   JSON: {json_output_file}")
    print(f"   Text: {text_output_file}")
    print(f"\n📊 Summary:")
    print(f"   Academic articles: {len(newsletter.academic_articles)}")
    for article in newsletter.academic_articles:
        print(f"      • [{article.source}] {article.title[:60]}...")
    print(f"\n   Tech News articles: {len(newsletter.technews_articles)}")
    for article in newsletter.technews_articles:
        print(f"      • [{article.source}] {article.title[:60]}...")
    print(f"\n{'='*60}\n")

    # 미리보기 출력
    print("\n📰 Newsletter Preview (first 800 characters):")
    print("=" * 60)
    print(newsletter_text[:800] + "...")
    print("=" * 60)


if __name__ == "__main__":
    main()
