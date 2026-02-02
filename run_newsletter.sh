#!/bin/bash
#
# AI Newsletter 자동 실행 스크립트
# 매일 아침 6시에 크롤링 → 큐레이팅 → 뉴스레터 생성
#

# 작업 디렉토리 설정
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 로그 파일 설정
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/newsletter_$(date +%Y%m%d_%H%M%S).log"

# 로깅 함수
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=========================================="
log "AI Newsletter Pipeline 시작"
log "=========================================="

# 가상환경 활성화
log "가상환경 활성화 중..."
source .venv/bin/activate

if [ $? -ne 0 ]; then
    log "❌ 가상환경 활성화 실패"
    exit 1
fi

log "✅ 가상환경 활성화 완료"

# 환경 변수 확인
if [ -z "$OPENAI_API_KEY" ] && [ ! -f .env ]; then
    log "⚠️  경고: OPENAI_API_KEY가 설정되지 않았습니다"
fi

# Pipeline 실행
log "파이프라인 실행 중..."
python pipeline.py >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    log "✅ 파이프라인 실행 완료"

    # 최신 뉴스레터 파일 경로
    LATEST_NEWSLETTER=$(ls -t data/newsletters/newsletter_*.txt 2>/dev/null | head -1)

    if [ -n "$LATEST_NEWSLETTER" ]; then
        log "📰 생성된 뉴스레터: $LATEST_NEWSLETTER"

        # 뉴스레터 미리보기 (처음 500자)
        log "=========================================="
        log "뉴스레터 미리보기:"
        log "=========================================="
        head -c 500 "$LATEST_NEWSLETTER" | tee -a "$LOG_FILE"
        echo "" | tee -a "$LOG_FILE"
        log "=========================================="
    fi
else
    log "❌ 파이프라인 실행 실패 (exit code: $?)"
    exit 1
fi

log "=========================================="
log "AI Newsletter Pipeline 완료"
log "=========================================="

# 로그 정리 (30일 이상 된 로그 삭제)
find "$LOG_DIR" -name "newsletter_*.log" -mtime +30 -delete

exit 0
