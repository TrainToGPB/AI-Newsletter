#!/usr/bin/env python3
"""
AI Newsletter Pipeline
크롤링 → 큐레이팅 전체 파이프라인 실행
"""

import subprocess
import sys


def main():
    """메인 파이프라인 실행"""
    print("=" * 60)
    print("AI Newsletter Pipeline")
    print("=" * 60)

    # Step 1: 크롤링
    print("\n[Step 1/3] Running crawler...")
    print("-" * 60)
    try:
        result = subprocess.run(
            [sys.executable, "crawler.py"],
            check=True,
            capture_output=False
        )
        print("\n✅ Crawler completed successfully")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Crawler failed with exit code {e.returncode}")
        sys.exit(1)

    # Step 2: 큐레이팅
    print("\n[Step 2/3] Running curator...")
    print("-" * 60)
    try:
        result = subprocess.run(
            [sys.executable, "curator.py"],
            check=True,
            capture_output=False
        )
        print("\n✅ Curator completed successfully")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Curator failed with exit code {e.returncode}")
        sys.exit(1)

    # Step 3: 뉴스레터 작성
    print("\n[Step 3/3] Running newsletter writer...")
    print("-" * 60)
    try:
        result = subprocess.run(
            [sys.executable, "news_writer.py"],
            check=True,
            capture_output=False
        )
        print("\n✅ Newsletter writer completed successfully")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Newsletter writer failed with exit code {e.returncode}")
        sys.exit(1)

    # 완료
    print("\n" + "=" * 60)
    print("✅ Pipeline complete!")
    print("=" * 60)
    print("\nResults:")
    print("  • Crawled data: data/crawled_data/")
    print("  • Curated results: data/curated/")
    print("  • Newsletter: data/newsletters/")
    print("=" * 60)


if __name__ == "__main__":
    main()
