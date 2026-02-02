#!/usr/bin/env python3
"""
Newsletter Source Crawler
크롤링한 페이지의 구조를 JSON 형태로 파싱하여 출력합니다.
"""

import json
import re
import time
import random
import requests
import hashlib
import asyncio
import aiohttp
from datetime import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional
from pathlib import Path

import trafilatura
from urllib.parse import urljoin, urlparse


@dataclass
class Article:
    """기사/논문 정보를 담는 데이터 클래스"""
    title: str
    url: str
    date: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {k: v for k, v in asdict(self).items() if v is not None}


class BaseSourceCrawler(ABC):
    """소스 크롤러의 기본 클래스"""

    def __init__(self, source_name: str, base_url: str, rate_limit: float = 1.0):
        self.source_name = source_name
        self.base_url = base_url
        self.rate_limit = rate_limit  # 요청 간 최소 대기 시간 (초)
        self.last_request_time = 0
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def _rate_limit_wait(self):
        """속도 제한을 위한 대기"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            wait_time = self.rate_limit - elapsed + random.uniform(0.1, 0.5)
            time.sleep(wait_time)
        self.last_request_time = time.time()

    def fetch_page(self, url: str) -> Optional[str]:
        """페이지 HTML 가져오기"""
        try:
            self._rate_limit_wait()
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

    def extract_with_trafilatura(self, html: str, url: str) -> Dict[str, Any]:
        """trafilatura를 사용하여 기본 정보 추출"""
        downloaded = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            include_links=True,
            output_format='json',
            url=url
        )

        if downloaded:
            return json.loads(downloaded)
        return {}

    def extract_metadata(self, html: str) -> Dict[str, Any]:
        """trafilatura로 메타데이터 추출"""
        return trafilatura.extract_metadata(html) or {}

    def extract_date_from_article(self, url: str) -> Optional[str]:
        """개별 기사 페이지에서 날짜 추출"""
        try:
            html = self.fetch_page(url)
            if not html:
                return None

            # trafilatura로 메타데이터 추출
            metadata = trafilatura.extract_metadata(html)
            if metadata and metadata.date:
                return metadata.date

            # JSON-LD 구조화된 데이터에서 날짜 찾기
            from lxml import html as lxml_html
            import re

            tree = lxml_html.fromstring(html)

            # JSON-LD script 태그 찾기
            json_ld_scripts = tree.xpath('//script[@type="application/ld+json"]')
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.text_content())
                    if isinstance(data, dict):
                        # datePublished, publishedDate, dateCreated 등 찾기
                        for key in ['datePublished', 'publishedDate', 'dateCreated', 'date']:
                            if key in data:
                                return data[key]
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                for key in ['datePublished', 'publishedDate', 'dateCreated', 'date']:
                                    if key in item:
                                        return item[key]
                except:
                    continue

            # meta 태그에서 날짜 찾기
            meta_date_selectors = [
                '//meta[@property="article:published_time"]/@content',
                '//meta[@name="publication_date"]/@content',
                '//meta[@name="date"]/@content',
                '//meta[@property="og:published_time"]/@content',
                '//meta[@name="pubdate"]/@content',
            ]

            for selector in meta_date_selectors:
                dates = tree.xpath(selector)
                if dates:
                    return dates[0]

            # time 태그에서 날짜 찾기
            time_tags = tree.xpath('//time/@datetime')
            if time_tags:
                return time_tags[0]

            return None
        except Exception as e:
            print(f"Error extracting date from {url}: {e}")
            return None

    @abstractmethod
    def parse_listing_page(self, html: str) -> List[Article]:
        """목록 페이지를 파싱하여 Article 리스트 반환"""
        pass

    def crawl(self, full_content: bool = False, extract_dates: bool = True) -> Dict[str, Any]:
        """크롤링 실행"""
        print(f"\n{'='*60}")
        print(f"Crawling: {self.source_name}")
        print(f"URL: {self.base_url}")
        print(f"{'='*60}\n")

        html = self.fetch_page(self.base_url)
        if not html:
            return {
                "source": self.source_name,
                "url": self.base_url,
                "error": "Failed to fetch page",
                "timestamp": datetime.now().isoformat()
            }

        # 목록 페이지 파싱
        articles = self.parse_listing_page(html)

        # 날짜가 없는 기사들에 대해 날짜 추출
        if extract_dates:
            articles_without_dates = [a for a in articles if not a.date]
            if articles_without_dates:
                print(f"Extracting dates for {len(articles_without_dates)} articles...")
                for i, article in enumerate(articles_without_dates, 1):
                    print(f"  [{i}/{len(articles_without_dates)}] {article.title[:50]}...")
                    date = self.extract_date_from_article(article.url)
                    if date:
                        article.date = date
                        print(f"    → Found date: {date}")

        # 전체 컨텐츠를 가져올 경우
        if full_content:
            print(f"Extracting full content for first 5 articles...")
            for article in articles[:5]:
                if article.url:
                    article_html = self.fetch_page(article.url)
                    if article_html:
                        extracted = self.extract_with_trafilatura(article_html, article.url)
                        article.content = extracted.get('text', '')

        result = {
            "source": self.source_name,
            "url": self.base_url,
            "timestamp": datetime.now().isoformat(),
            "articles_count": len(articles),
            "articles": [article.to_dict() for article in articles]
        }

        return result


class AlphaXivCrawler(BaseSourceCrawler):
    """alphaXiv 크롤러 - Playwright 사용"""

    def __init__(self):
        super().__init__("alphaxiv", "https://www.alphaxiv.org", rate_limit=2.0)

    def extract_date_from_article(self, url: str) -> Optional[str]:
        """AlphaXiv 기사 페이지에서 날짜 추출 - URL 변환"""
        # /abs/ 를 /ko/overview/ 로 변경
        if '/abs/' in url:
            url = url.replace('/abs/', '/ko/overview/')

        # 부모 클래스의 extract_date_from_article 호출
        return super().extract_date_from_article(url)

    def fetch_page(self, url: str) -> Optional[str]:
        """Playwright를 사용하여 JavaScript 렌더링된 페이지 가져오기"""
        try:
            from playwright.sync_api import sync_playwright

            # 속도 제한 적용
            self._rate_limit_wait()

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                print(f"Playwright로 페이지 로딩 중: {url}")
                page.goto(url, wait_until="networkidle", timeout=30000)

                # 논문 목록이 로드될 때까지 대기
                page.wait_for_timeout(2000)

                html = page.content()
                browser.close()
                return html
        except Exception as e:
            print(f"Playwright 페이지 로딩 실패: {e}")
            return None

    def parse_listing_page(self, html: str) -> List[Article]:
        """alphaXiv 목록 페이지 파싱"""
        from lxml import html as lxml_html

        articles = []
        seen_urls = set()
        tree = lxml_html.fromstring(html)

        # 논문 카드나 링크 찾기
        # alphaXiv의 구조에 맞게 선택자 조정
        selectors = [
            "//a[contains(@href, '/abs/')]",  # arXiv 스타일 논문 링크
            "//article//a",
            "//div[contains(@class, 'paper')]//a",
            "//div[contains(@class, 'card')]//a",
        ]

        for selector in selectors:
            links = tree.xpath(selector)
            if links:
                print(f"Found {len(links)} links with selector: {selector}")

                for link in links:
                    article = self._parse_paper_link(link)
                    if article and article.url not in seen_urls:
                        articles.append(article)
                        seen_urls.add(article.url)

                if articles:
                    break

        return articles[:20]  # 최대 20개만

    def _parse_paper_link(self, link) -> Optional[Article]:
        """개별 논문 링크 파싱"""
        try:
            title = link.text_content().strip()
            url = link.get('href', '')

            # 제목이 너무 짧거나 네비게이션 링크는 스킵
            if not title or len(title) < 10:
                return None

            # 상대 URL을 절대 URL로 변환
            if url and not url.startswith('http'):
                url = urljoin(self.base_url, url)

            # 부모 요소에서 메타데이터 찾기
            parent = link.getparent()
            date = None
            author = None
            description = None

            for _ in range(3):
                if parent is None:
                    break

                # 날짜 찾기
                if date is None:
                    date_elem = parent.xpath(".//*[contains(@class, 'date') or contains(@class, 'time')]")
                    if date_elem:
                        date = date_elem[0].text_content().strip()

                # 저자 찾기
                if author is None:
                    author_elem = parent.xpath(".//*[contains(@class, 'author')]")
                    if author_elem:
                        author = author_elem[0].text_content().strip()

                # 설명/초록 찾기
                if description is None:
                    desc_elem = parent.xpath(".//p")
                    if desc_elem:
                        desc_text = desc_elem[0].text_content().strip()
                        if desc_text and desc_text != title:
                            description = desc_text

                parent = parent.getparent()

            return Article(
                title=title,
                url=url,
                date=date,
                author=author,
                description=description
            )
        except Exception as e:
            print(f"Error parsing paper link: {e}")
            return None


class HuggingFaceBlogCrawler(BaseSourceCrawler):
    """Hugging Face Blog 크롤러"""

    def __init__(self):
        super().__init__("hf_blog", "https://huggingface.co/blog", rate_limit=1.5)

    def parse_listing_page(self, html: str) -> List[Article]:
        """Hugging Face 블로그 목록 페이지 파싱"""
        from lxml import html as lxml_html

        articles = []
        tree = lxml_html.fromstring(html)

        # Hugging Face 블로그 구조 분석
        selectors = [
            "//article",
            "//div[contains(@class, 'blog')]//a[contains(@href, '/blog/')]",
            "//a[contains(@href, '/blog/') and .//h2]",
            "//div[contains(@class, 'post')]",
        ]

        for selector in selectors:
            elements = tree.xpath(selector)
            if elements:
                print(f"Found {len(elements)} elements with selector: {selector}")

                for elem in elements[:20]:
                    article = self._parse_blog_post(elem)
                    if article:
                        articles.append(article)

                if articles:
                    break

        return articles

    def _parse_blog_post(self, elem) -> Optional[Article]:
        """개별 블로그 포스트 파싱"""
        try:
            title_elem = elem.xpath(".//h1 | .//h2 | .//h3")
            title = title_elem[0].text_content().strip() if title_elem else ""

            link_elem = elem if elem.tag == 'a' else elem.xpath(".//a[@href]")
            if isinstance(link_elem, list):
                url = link_elem[0].get('href', '') if link_elem else ""
            else:
                url = link_elem.get('href', '')

            if url and not url.startswith('http'):
                url = urljoin(self.base_url, url)

            if not title or not url:
                return None

            date_elem = elem.xpath(".//*[contains(@class, 'date') or contains(text(), '20')]")
            date = date_elem[0].text_content().strip() if date_elem else None

            author_elem = elem.xpath(".//*[contains(@class, 'author')]")
            author = author_elem[0].text_content().strip() if author_elem else None

            desc_elem = elem.xpath(".//p[not(ancestor::*[contains(@class, 'metadata')])]")
            description = desc_elem[0].text_content().strip() if desc_elem else None

            # 태그 찾기
            tag_elems = elem.xpath(".//*[contains(@class, 'tag')]")
            tags = [tag.text_content().strip() for tag in tag_elems] if tag_elems else None

            return Article(
                title=title,
                url=url,
                date=date,
                author=author,
                description=description,
                tags=tags
            )
        except Exception as e:
            print(f"Error parsing blog post: {e}")
            return None


class VentureBeatCrawler(BaseSourceCrawler):
    """VentureBeat AI 크롤러"""

    def __init__(self):
        super().__init__("venturebeat", "https://venturebeat.com/category/ai/", rate_limit=2.0)

    def parse_listing_page(self, html: str) -> List[Article]:
        """VentureBeat 목록 페이지 파싱"""
        from lxml import html as lxml_html

        articles = []
        tree = lxml_html.fromstring(html)

        # article 태그에서 기사 추출
        article_elements = tree.xpath("//article")
        print(f"Found {len(article_elements)} article elements")

        for elem in article_elements:
            article = self._parse_article(elem)
            if article:
                articles.append(article)

        return articles

    def _parse_article(self, elem) -> Optional[Article]:
        """개별 기사 파싱"""
        try:
            # h2 또는 h3 안의 링크에서 제목 추출
            title_elem = elem.xpath('.//h2//a | .//h3//a')
            if not title_elem:
                return None

            title = title_elem[0].text_content().strip()
            url = title_elem[0].get('href', '')

            if not title or not url:
                return None

            if url and not url.startswith('http'):
                url = urljoin(self.base_url, url)

            # 날짜 찾기
            date_elem = elem.xpath(".//*[contains(@class, 'date') or contains(@class, 'time')]")
            date = date_elem[0].text_content().strip() if date_elem else None

            # 저자 찾기
            author_elem = elem.xpath(".//*[contains(@class, 'author')]")
            author = author_elem[0].text_content().strip() if author_elem else None

            # 설명 찾기 (p 태그, 단 이미지 alt는 제외)
            desc_elem = elem.xpath(".//p[not(parent::figcaption)]")
            description = desc_elem[0].text_content().strip() if desc_elem else None

            # 카테고리/태그 찾기
            tag_elems = elem.xpath(".//*[contains(@class, 'category') or contains(@class, 'tag')]")
            tags = [tag.text_content().strip() for tag in tag_elems] if tag_elems else None

            return Article(
                title=title,
                url=url,
                date=date,
                author=author,
                description=description,
                tags=tags
            )
        except Exception as e:
            print(f"Error parsing article: {e}")
            return None


def url_to_hash(url: str) -> str:
    """URL을 짧은 hash로 변환 (8자)"""
    return hashlib.md5(url.encode()).hexdigest()[:8]


def fetch_article_content(articles: List[Dict[str, Any]], output_base: Path = Path("data/articles")) -> None:
    """
    선택된 기사들의 본문을 markdown으로 추출하여 저장

    Args:
        articles: [{"source": "alphaxiv", "url": "...", "title": "...", "date": "..."}, ...]
        output_base: 저장 기본 경로
    """
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })

    for article in articles:
        try:
            source = article.get('source', 'unknown')
            url = article.get('url', '')
            title = article.get('title', 'Untitled')
            date = article.get('date', '')

            if not url:
                print(f"⚠️  URL이 없는 기사 건너뜀: {title}")
                continue

            # 소스별 디렉토리 생성
            source_dir = output_base / source
            source_dir.mkdir(parents=True, exist_ok=True)

            # URL hash로 파일명 생성
            filename = f"{url_to_hash(url)}.md"
            output_file = source_dir / filename

            # 이미 파일이 존재하면 건너뜀
            if output_file.exists():
                print(f"⏭️  이미 존재하는 파일 건너뜀: {output_file}")
                continue

            print(f"\n{'='*60}")
            print(f"📥 Content 추출 중: {title[:50]}...")
            print(f"   Source: {source}")
            print(f"   URL: {url}")

            # alphaxiv의 경우 URL 변환 (/abs/ → /ko/overview/)
            fetch_url = url
            if source == 'alphaxiv' and '/abs/' in url:
                fetch_url = url.replace('/abs/', '/ko/overview/')
                print(f"   → 변환된 URL: {fetch_url}")

            # HTML 가져오기
            if source == 'alphaxiv':
                # alphaxiv는 playwright 사용
                try:
                    from playwright.sync_api import sync_playwright

                    with sync_playwright() as p:
                        browser = p.chromium.launch(headless=True)
                        page = browser.new_page()

                        print(f"   🎭 Playwright로 페이지 로딩 중...")
                        page.goto(fetch_url, wait_until="networkidle", timeout=30000)
                        page.wait_for_timeout(2000)  # 추가 대기

                        html = page.content()
                        browser.close()
                except Exception as e:
                    print(f"   ⚠️  Playwright 로딩 실패: {e}")
                    # fallback to requests
                    response = session.get(fetch_url, timeout=30)
                    response.raise_for_status()
                    html = response.text
            else:
                # 나머지는 requests 사용
                response = session.get(fetch_url, timeout=30)
                response.raise_for_status()
                html = response.text

            # trafilatura로 markdown 추출
            markdown_content = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                include_links=True,
                include_images=True,  # 이미지 포함
                include_formatting=True,
                output_format='markdown',
                url=url
            )

            if not markdown_content:
                print(f"⚠️  Content 추출 실패: {title}")
                continue

            # hf_blog 헤더 포맷 수정 (깨진 링크 제거)
            # 패턴: ### \n [ \n ](url) \n Title → ### Title
            markdown_content = re.sub(
                r'(#{1,6})[\s\n]+\[[\s\n]*\]\([^)]+\)[\s\n]+(.+?)(?=\n)',
                r'\1 \2',
                markdown_content,
                flags=re.MULTILINE
            )

            # 볼드 뒤에 공백 없이 소문자가 오는 경우 공백 추가
            # **AssetOpsBench**is → **AssetOpsBench** is
            markdown_content = re.sub(
                r'\*\*([^*]+)\*\*([a-z])',
                r'**\1** \2',
                markdown_content
            )

            # 연속된 볼드 항목들을 bullet list로 변환
            def fix_consecutive_bold_items(match):
                line = match.group(0)
                # **content** 또는 **content**text 형태를 모두 찾기
                items = re.findall(r'\*\*([^*]+)\*\*([^*]*?)(?=\*\*|$)', line)
                if len(items) >= 2:  # 2개 이상의 항목이 있을 때만
                    result = []
                    for bold, text in items:
                        text = text.strip()
                        if text:
                            result.append(f'- **{bold.strip()}** {text}')
                        else:
                            result.append(f'- **{bold.strip()}**')
                    return '\n'.join(result)
                return line

            # 패턴1: **content**text**content2**text2 형태
            # 패턴2: **content****content2****content3** 형태 (텍스트 없이 연속)
            markdown_content = re.sub(
                r'^(\*\*[^*\n]+\*\*[^*\n]*){2,}$',  # 2개 이상의 **content** 또는 **content**text
                fix_consecutive_bold_items,
                markdown_content,
                flags=re.MULTILINE
            )

            # YAML frontmatter 생성
            # 제목에서 따옴표 escape
            escaped_title = title.replace('"', '\\"')
            frontmatter = f"""---
title: "{escaped_title}"
url: "{url}"
date: "{date}"
source: "{source}"
---

"""

            # 최종 markdown 파일 내용
            final_content = frontmatter + markdown_content

            # 파일 저장
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(final_content)

            print(f"✅ 저장 완료: {output_file}")
            print(f"   파일 크기: {len(final_content)} bytes")

            # 속도 제한 (1초 대기)
            time.sleep(1)

        except Exception as e:
            print(f"❌ Error processing {article.get('title', 'unknown')}: {e}")
            import traceback
            traceback.print_exc()


class AITimesCrawler(BaseSourceCrawler):
    """AI Times 크롤러 (한국)"""

    def __init__(self):
        super().__init__("ai_times", "https://www.aitimes.com/", rate_limit=1.5)

    def parse_listing_page(self, html: str) -> List[Article]:
        """AI Times 목록 페이지 파싱"""
        from lxml import html as lxml_html

        articles = []
        seen_urls = set()
        tree = lxml_html.fromstring(html)

        # article 태그 내의 링크만 추출 (메인 뉴스 영역)
        # 또는 auto-article 클래스 내의 링크
        article_links = tree.xpath(
            '//article//a[contains(@href, "articleView.html")] | '
            '//div[contains(@class, "auto-article")]//a[contains(@href, "articleView.html")]'
        )
        print(f"Found {len(article_links)} article links in main sections")

        for link in article_links:
            article = self._parse_news_link(link)
            if article and article.url not in seen_urls:
                # 중복 제거 및 특정 카테고리 제외
                if (len(article.title) > 10 and
                    not article.title.startswith('[AI웹툰]') and
                    not article.title.startswith('NOT MY BLOOD')):
                    articles.append(article)
                    seen_urls.add(article.url)

                    # 최대 30개만 추출
                    if len(articles) >= 30:
                        break

        return articles

    def _parse_news_link(self, link) -> Optional[Article]:
        """개별 뉴스 링크 파싱"""
        try:
            title = link.text_content().strip()
            url = link.get('href', '')

            # 제목이 없거나 너무 짧으면 스킵
            if not title or len(title) < 5:
                return None

            if url and not url.startswith('http'):
                url = urljoin(self.base_url, url)

            # 부모 요소에서 추가 정보 추출
            parent = link.getparent()
            date = None
            author = None
            description = None

            # 여러 단계 위로 올라가면서 메타데이터 찾기
            for _ in range(3):
                if parent is None:
                    break

                # 날짜 찾기
                if date is None:
                    date_elem = parent.xpath(".//*[contains(@class, 'date') or contains(@class, 'time') or contains(@class, 'byline')]")
                    if date_elem:
                        date = date_elem[0].text_content().strip()

                # 저자 찾기
                if author is None:
                    author_elem = parent.xpath(".//*[contains(@class, 'author') or contains(@class, 'writer')]")
                    if author_elem:
                        author = author_elem[0].text_content().strip()

                # 설명 찾기
                if description is None:
                    desc_elem = parent.xpath(".//dd | .//p")
                    if desc_elem:
                        desc_text = desc_elem[0].text_content().strip()
                        # 제목과 다른 경우만 설명으로 사용
                        if desc_text and desc_text != title:
                            description = desc_text

                parent = parent.getparent()

            return Article(
                title=title,
                url=url,
                date=date,
                author=author,
                description=description
            )
        except Exception as e:
            print(f"Error parsing news link: {e}")
            return None


def test_fetch_top_articles() -> None:
    """소스 별 상위 1개 기사의 content를 추출하여 저장 (테스트용)"""
    print(f"\n{'='*60}")
    print("테스트: 소스별 상위 1개 기사 content 추출")
    print(f"{'='*60}\n")

    # data/crawled_data/ 에서 가장 최근 파일 찾기
    crawled_data_dir = Path("data/crawled_data")
    if not crawled_data_dir.exists():
        print("❌ data/crawled_data/ 폴더가 없습니다. 먼저 크롤링을 실행하세요.")
        return

    json_files = list(crawled_data_dir.glob("crawler_results_*.json"))
    if not json_files:
        print("❌ 크롤링 결과 파일이 없습니다. 먼저 크롤링을 실행하세요.")
        return

    # 가장 최근 파일 선택 (파일명 정렬)
    latest_file = sorted(json_files)[-1]
    print(f"📂 로딩: {latest_file}\n")

    # JSON 로드
    with open(latest_file, 'r', encoding='utf-8') as f:
        results = json.load(f)

    # 각 소스에서 첫 번째 기사 선택
    test_articles = []
    for source_data in results:
        source_name = source_data.get('source', 'unknown')
        articles = source_data.get('articles', [])

        if articles:
            # 첫 번째 기사 선택
            first_article = articles[0].copy()
            first_article['source'] = source_name  # source 정보 추가
            test_articles.append(first_article)
            print(f"✓ {source_name}: {first_article.get('title', 'N/A')[:60]}...")

    print(f"\n총 {len(test_articles)}개 기사 선택됨\n")

    # content 추출 및 저장
    fetch_article_content(test_articles)

    print(f"\n{'='*60}")
    print("✅ 테스트 완료!")
    print(f"{'='*60}")


def extract_introduction(markdown: str, source: str) -> Optional[str]:
    """
    마크다운에서 introduction 추출
    1. 첫 번째 헤더를 찾는다
    2. 헤더 이전에 의미있는 텍스트가 있으면 → 그것을 사용
    3. 헤더가 첫 줄이면 → 첫 헤더 다음부터 두 번째 헤더까지 또는 첫 이중 개행까지
    4. 헤더가 없으면 → 첫 이중 개행 이전까지
    5. 모두 없으면 → 최대 500자
    """
    if not markdown:
        return None

    try:
        # 첫 번째 헤더 찾기
        first_header = re.search(r'^#{1,6}\s', markdown, re.MULTILINE)

        if first_header:
            # 헤더 이전 텍스트 확인
            before_header = markdown[:first_header.start()].strip()

            if before_header and len(before_header) > 20:
                # 헤더 이전에 충분한 텍스트가 있으면 그것을 사용
                intro = before_header
            else:
                # 헤더가 첫 줄이면, 헤더 다음부터 추출
                after_header_start = first_header.end()
                rest_content = markdown[after_header_start:].strip()

                # 두 번째 헤더 찾기
                second_header = re.search(r'^#{1,6}\s', rest_content, re.MULTILINE)

                if second_header:
                    # 두 번째 헤더 이전까지
                    intro = rest_content[:second_header.start()].strip()
                elif '\n\n' in rest_content:
                    # 첫 이중 개행 이전까지
                    intro = rest_content.split('\n\n')[0].strip()
                else:
                    # 첫 500자
                    intro = rest_content[:500].strip()
        else:
            # 헤더가 없으면
            if '\n\n' in markdown:
                intro = markdown.split('\n\n')[0].strip()
            else:
                intro = markdown[:500].strip()

        return intro if intro else None
    except Exception as e:
        print(f"  ⚠️  Introduction 추출 실패: {e}")
        return None


async def fetch_description_async(session: aiohttp.ClientSession, url: str, source: str) -> Optional[str]:
    """비동기로 URL에서 description 추출"""
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
            if response.status != 200:
                return None

            html = await response.text()

            # trafilatura로 markdown 추출 (동기 함수이므로 그대로 사용)
            markdown_content = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=False,
                include_links=False,
                include_images=False,
                include_formatting=False,
                output_format='markdown',
                url=url
            )

            if not markdown_content:
                return None

            # Introduction 추출
            intro = extract_introduction(markdown_content, source)
            return intro

    except asyncio.TimeoutError:
        print(f"  ⏱️  Timeout: {url}")
        return None
    except Exception as e:
        print(f"  ⚠️  Error fetching {url}: {e}")
        return None


async def enrich_articles_with_descriptions(articles: List[Dict[str, Any]], source: str) -> List[Dict[str, Any]]:
    """기사 목록에 description 추가 (병렬 처리)"""
    if not articles:
        return articles

    print(f"\n📝 Fetching descriptions for {source} ({len(articles)} articles)...")

    # aiohttp session 생성
    connector = aiohttp.TCPConnector(limit=10)  # 동시 연결 제한
    async with aiohttp.ClientSession(
        connector=connector,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    ) as session:
        # 모든 기사에 대해 병렬로 description 추출
        tasks = []
        for article in articles:
            url = article.get('url')
            if url and not article.get('description'):  # description이 없는 경우만
                task = fetch_description_async(session, url, source)
                tasks.append((article, task))
            else:
                tasks.append((article, None))

        # 병렬 실행
        for i, (article, task) in enumerate(tasks):
            if task:
                description = await task
                if description:
                    article['description'] = description
                    print(f"  ✓ [{i+1}/{len(articles)}] {article.get('title', 'N/A')[:50]}...")
                else:
                    print(f"  ✗ [{i+1}/{len(articles)}] {article.get('title', 'N/A')[:50]}...")

    print(f"✅ Description fetching complete for {source}")
    return articles


def main():
    """메인 실행 함수"""
    # 타임스탬프 생성 (YYMMDD_hhmm 형식)
    timestamp = datetime.now().strftime("%y%m%d_%H%M")

    # 저장 경로 설정
    output_dir = Path("data/crawled_data")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"crawler_results_{timestamp}.json"

    # 동일한 파일이 이미 존재하는지 확인
    if output_file.exists():
        print(f"\n{'='*60}")
        print(f"크롤링 결과 파일이 이미 존재합니다: {output_file}")
        print(f"동일한 시간대에 이미 크롤링이 완료되었습니다.")
        print(f"불필요한 크롤링을 건너뜁니다.")
        print(f"{'='*60}\n")
        return

    crawlers = [
        AlphaXivCrawler(),
        HuggingFaceBlogCrawler(),
        VentureBeatCrawler(),
        AITimesCrawler(),
    ]

    results = []

    for crawler in crawlers:
        try:
            result = crawler.crawl(full_content=False)

            # Description enrichment (비동기)
            # alphaxiv는 이미 description이 있으므로 제외
            source_name = result['source']
            articles = result.get('articles', [])

            if articles and source_name != 'alphaxiv':
                # asyncio로 병렬 처리
                enriched_articles = asyncio.run(
                    enrich_articles_with_descriptions(articles, source_name)
                )
                result['articles'] = enriched_articles

            results.append(result)

            # 결과 출력
            print(f"\n{'='*60}")
            print(f"Results for {result['source']}:")
            print(f"{'='*60}")
            print(f"Total articles: {len(result.get('articles', []))}")
            articles_with_desc = sum(1 for a in result.get('articles', []) if a.get('description'))
            print(f"Articles with description: {articles_with_desc}")
            print()

        except Exception as e:
            print(f"Error crawling {crawler.source_name}: {e}")
            import traceback
            traceback.print_exc()

    # 전체 결과를 파일로 저장
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"All results saved to: {output_file}")
    print(f"Total sources crawled: {len(results)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
