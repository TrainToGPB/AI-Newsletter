#!/usr/bin/env python3
"""
AI Newsletter Curator System
LangChain + ChatOpenAI를 사용하여 크롤링된 기사를 큐레이션합니다.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

from models import CurationResult, SelectedArticle
from crawler import fetch_article_content


def load_prompt(path: str) -> str:
    """프롬프트 마크다운 파일 로드"""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def load_latest_crawled_data() -> Dict[str, Any]:
    """
    data/crawled_data/에서 가장 최근 크롤링 결과 로드

    Returns:
        {"alphaxiv": [...], "hf_blog": [...], "venturebeat": [...], "ai_times": [...]}
    """
    crawled_data_dir = Path("data/crawled_data")
    if not crawled_data_dir.exists():
        raise FileNotFoundError(
            f"Crawled data directory not found: {crawled_data_dir}\n"
            "Please run crawler.py first."
        )

    # 가장 최근 JSON 파일 찾기
    json_files = list(crawled_data_dir.glob("crawler_results_*.json"))
    if not json_files:
        raise FileNotFoundError(
            f"No crawler results found in {crawled_data_dir}\n"
            "Please run crawler.py first."
        )

    latest_file = sorted(json_files)[-1]
    print(f"📂 Loading crawled data: {latest_file}")

    with open(latest_file, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)

    # 소스별로 재구성
    data_by_source = {}
    for source_data in raw_data:
        source_name = source_data.get('source', 'unknown')
        articles = source_data.get('articles', [])
        data_by_source[source_name] = articles
        print(f"  ✓ {source_name}: {len(articles)} articles")

    return data_by_source


def apply_duplicate_filtering(data_by_source: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
    """
    Filter out articles that were already sent in past newsletters

    Args:
        data_by_source: Dict mapping source name to article list

    Returns:
        Filtered dict with duplicates removed
    """
    from memory import load_sent_urls, filter_duplicate_articles, get_duplicate_stats

    print(f"\n🔍 Checking for duplicate articles...")
    try:
        sent_urls = load_sent_urls(days_back=14)
        print(f"   Loaded {len(sent_urls)} URLs from past 2 weeks")

        # Log statistics
        stats = get_duplicate_stats(data_by_source, sent_urls)
        for source, counts in stats.items():
            if counts['duplicates'] > 0:
                print(f"   ⚠️  {source}: {counts['duplicates']}/{counts['total']} duplicates")
            else:
                print(f"   ✓ {source}: {counts['new']}/{counts['total']} new articles")

        # Filter duplicates
        data_by_source, dup_counts = filter_duplicate_articles(data_by_source, sent_urls)

        total_filtered = sum(dup_counts.values())
        if total_filtered > 0:
            print(f"   🚫 Filtered {total_filtered} duplicate articles")
        else:
            print(f"   ✅ No duplicates found")

    except FileNotFoundError:
        print(f"   ℹ️  No previous newsletters found (first run)")
    except Exception as e:
        print(f"   ⚠️  Error loading memory: {e}")
        print(f"   ℹ️  Continuing without duplicate filtering")

    return data_by_source


def format_articles_xml(articles: List[Dict[str, Any]]) -> str:
    """
    기사 리스트를 XML 형식으로 포맷팅

    Args:
        articles: 기사 목록
        source: 소스 이름

    Returns:
        XML 형식 문자열
    """
    xml_parts = []
    for idx, article in enumerate(articles):
        title = article.get('title', 'No title')
        url = article.get('url', '')
        date = article.get('date', '')
        description = article.get('description', '')

        xml_parts.append(f"<article index='{idx}'>")
        xml_parts.append(f"<title>{title}</title>")
        xml_parts.append(f"<url>{url}</url>")
        xml_parts.append(f"<date>{date}</date>")
        if description:
            xml_parts.append(f"<description>{description}</description>")
        xml_parts.append(f"</article>")
    
    return '\n'.join(xml_parts)


def enrich_selected_articles(
    result: CurationResult,
    articles_by_source: Dict[str, List[Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    """
    LLM 결과에 원본 데이터의 url, description 추가

    Args:
        result: CurationResult (LLM 응답)
        articles_by_source: 소스별 기사 목록

    Returns:
        enriched articles with url and description
    """
    enriched = []
    for article in result.selected_articles:
        source_articles = articles_by_source.get(article.source, [])
        if article.index < len(source_articles):
            original = source_articles[article.index]
            enriched.append({
                "source": article.source,
                "title": article.title,
                "url": original.get("url", ""),
                "description": original.get("description", ""),
                "reason_for_selection": article.reason_for_selection
            })
    return enriched


def curate_category(
    llm: ChatOpenAI,
    prompt_template: str,
    articles_by_source: Dict[str, List[Dict[str, Any]]],
    category: str
) -> CurationResult:
    """
    카테고리별 큐레이션 수행

    Args:
        llm: ChatOpenAI 모델
        prompt_template: 프롬프트 템플릿 ('{articles_xml}' 포함)
        articles_by_source: 소스별 기사 목록
        category: "academic" 또는 "technews"

    Returns:
        CurationResult
    """
    # 모든 소스의 기사를 XML로 변환
    xml_parts = []
    for source, articles in articles_by_source.items():
        if articles:
            xml_parts.append(format_articles_xml(articles))

    articles_xml = '\n\n'.join(xml_parts)

    # 프롬프트 생성
    prompt = prompt_template.replace('{articles_xml}', articles_xml)

    # LLM with structured output
    structured_llm = llm.with_structured_output(CurationResult)

    print(f"\n🤖 Curating {category}...")
    print(f"   Total sources: {len(articles_by_source)}")
    print(f"   Total articles: {sum(len(articles) for articles in articles_by_source.values())}")

    # 큐레이션 실행
    result = structured_llm.invoke(prompt)

    print(f"   ✓ Selected {len(result.selected_articles)} articles")

    return result


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
    print("AI Newsletter Curator")
    print(f"{'='*60}\n")

    # 1. 크롤링 데이터 로드
    crawled_data = load_latest_crawled_data()

    # 1.5. 중복 필터링 (최근 2주간 뉴스레터에 나간 기사 제외)
    crawled_data = apply_duplicate_filtering(crawled_data)

    # 2. LLM 초기화 (gpt-5-mini)
    print(f"\n🔧 Initializing LLM (gpt-5-mini)...")
    llm = ChatOpenAI(
        model="gpt-5-mini",
        model_kwargs={
            "reasoning_effort": "medium",  # low, medium, high
            "max_completion_tokens": 2000
        }
    )
    print("   ✓ LLM initialized")

    # 3. 프롬프트 로드
    academic_prompt = load_prompt("prompts/academic_curator.md")
    technews_prompt = load_prompt("prompts/technews_curator.md")

    # 4. Academic 큐레이션 (alphaxiv + hf_blog)
    academic_sources = {
        "alphaxiv": crawled_data.get("alphaxiv", []),
        "hf_blog": crawled_data.get("hf_blog", [])
    }

    academic_result = curate_category(
        llm=llm,
        prompt_template=academic_prompt,
        articles_by_source=academic_sources,
        category="academic"
    )

    # 5. Tech News 큐레이션 (venturebeat + ai_times)
    technews_sources = {
        "venturebeat": crawled_data.get("venturebeat", []),
        "ai_times": crawled_data.get("ai_times", [])
    }

    technews_result = curate_category(
        llm=llm,
        prompt_template=technews_prompt,
        articles_by_source=technews_sources,
        category="technews"
    )

    # 6. 결과 저장 (url, description 포함)
    timestamp = datetime.now().strftime("%y%m%d_%H%M")
    output_dir = Path("data/curated")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"curated_{timestamp}.json"

    # Enrich with url and description
    academic_enriched = enrich_selected_articles(academic_result, academic_sources)
    technews_enriched = enrich_selected_articles(technews_result, technews_sources)

    # JSON 직렬화 가능한 형태로 변환
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "academic": {
            "category": "academic",
            "selected_articles": academic_enriched
        },
        "technews": {
            "category": "technews",
            "selected_articles": technews_enriched
        }
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"✅ Curation Complete!")
    print(f"{'='*60}")
    print(f"\n📄 Results saved to: {output_file}")
    print(f"\n📊 Summary:")
    print(f"   Academic: {len(academic_enriched)} articles selected")
    for article in academic_enriched:
        print(f"      • [{article['source']}] {article['title'][:60]}...")
    print(f"\n   Tech News: {len(technews_enriched)} articles selected")
    for article in technews_enriched:
        print(f"      • [{article['source']}] {article['title'][:60]}...")
    print(f"\n{'='*60}\n")

    # 7. 큐레이션된 기사들을 마크다운으로 저장
    print(f"\n{'='*60}")
    print("📝 Saving curated articles as markdown...")
    print(f"{'='*60}\n")

    all_selected_articles = academic_enriched + technews_enriched
    fetch_article_content(all_selected_articles)


if __name__ == "__main__":
    main()
