#!/usr/bin/env python3
"""
Memory System for AI Newsletter
Prevents duplicate articles by tracking URLs from past newsletters.
"""

from typing import Set, List, Dict, Any
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
import json


def normalize_url(url: str) -> str:
    """
    Normalize URL for duplicate detection.

    Handles:
    - Case-insensitive domains
    - Trailing slashes
    - URL fragments (#anchor)
    - Common tracking parameters (utm_*, ref, source)

    Args:
        url: Raw URL string

    Returns:
        Normalized URL string
    """
    if not url:
        return ""

    try:
        parsed = urlparse(url)

        # Remove tracking params
        tracking_params = {
            'utm_source', 'utm_medium', 'utm_campaign',
            'utm_term', 'utm_content', 'ref', 'source'
        }

        query = ''
        if parsed.query:
            params = parse_qs(parsed.query)
            filtered = {k: v for k, v in params.items()
                       if k.lower() not in tracking_params}
            if filtered:
                query = urlencode(filtered, doseq=True)

        # Rebuild without fragment, normalized domain, no trailing slash
        path = parsed.path.rstrip('/') if parsed.path != '/' else parsed.path

        normalized = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            parsed.params,
            query,
            ''  # Remove fragment
        ))

        return normalized
    except Exception:
        # If URL parsing fails, return original
        return url


def load_sent_urls(
    newsletters_dir: Path = Path("data/newsletters"),
    days_back: int = 14
) -> Set[str]:
    """
    Load all URLs from newsletters sent in the last N days.

    Args:
        newsletters_dir: Path to newsletters directory
        days_back: Number of days to look back

    Returns:
        Set of normalized URLs

    Raises:
        FileNotFoundError: If newsletters_dir doesn't exist
    """
    if not newsletters_dir.exists():
        raise FileNotFoundError(f"Newsletter directory not found: {newsletters_dir}")

    cutoff_time = datetime.now() - timedelta(days=days_back)
    sent_urls = set()

    # Find all newsletter JSON files
    json_files = list(newsletters_dir.glob("newsletter_*.json"))

    for json_file in json_files:
        try:
            # Check file modification time
            file_mtime = datetime.fromtimestamp(json_file.stat().st_mtime)

            if file_mtime < cutoff_time:
                continue  # Skip files older than cutoff

            # Load newsletter
            with open(json_file, 'r', encoding='utf-8') as f:
                newsletter = json.load(f)

            # Extract URLs from academic_articles
            for article in newsletter.get('academic_articles', []):
                url = article.get('url', '')
                if url:
                    sent_urls.add(normalize_url(url))

            # Extract URLs from technews_articles
            for article in newsletter.get('technews_articles', []):
                url = article.get('url', '')
                if url:
                    sent_urls.add(normalize_url(url))

        except Exception as e:
            # Log but don't fail - continue with other files
            print(f"   ⚠️  Error reading {json_file.name}: {e}")
            continue

    return sent_urls


def filter_duplicate_articles(
    articles_by_source: Dict[str, List[Dict[str, Any]]],
    sent_urls: Set[str]
) -> tuple[Dict[str, List[Dict[str, Any]]], Dict[str, int]]:
    """
    Filter out articles that were already sent.

    Args:
        articles_by_source: Dict mapping source name to article list
        sent_urls: Set of normalized URLs already sent

    Returns:
        Tuple of:
        - filtered_articles_by_source: Same structure with duplicates removed
        - duplicate_counts: Dict mapping source to number of duplicates filtered
    """
    filtered = {}
    duplicate_counts = {}

    for source, articles in articles_by_source.items():
        new_articles = []
        dup_count = 0

        for article in articles:
            url = article.get('url', '')
            normalized = normalize_url(url)

            if normalized and normalized in sent_urls:
                dup_count += 1
            else:
                new_articles.append(article)

        filtered[source] = new_articles
        duplicate_counts[source] = dup_count

    return filtered, duplicate_counts


def get_duplicate_stats(
    articles_by_source: Dict[str, List[Dict[str, Any]]],
    sent_urls: Set[str]
) -> Dict[str, Dict[str, int]]:
    """
    Get duplicate statistics without filtering (for logging).

    Args:
        articles_by_source: Dict mapping source name to article list
        sent_urls: Set of normalized URLs already sent

    Returns:
        Dict mapping source to {"total": N, "duplicates": M, "new": K}
    """
    stats = {}

    for source, articles in articles_by_source.items():
        total = len(articles)
        duplicates = 0

        for article in articles:
            url = article.get('url', '')
            normalized = normalize_url(url)
            if normalized and normalized in sent_urls:
                duplicates += 1

        stats[source] = {
            'total': total,
            'duplicates': duplicates,
            'new': total - duplicates
        }

    return stats
