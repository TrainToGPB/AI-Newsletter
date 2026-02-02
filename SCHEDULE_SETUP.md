# 매일 자동 실행 설정 가이드

AI Newsletter를 매일 아침 6시에 자동으로 실행하도록 설정하는 방법입니다.

## 방법 1: launchd 사용 (macOS, 권장)

### 1. launchd 설정 파일 복사

```bash
# LaunchAgents 디렉토리로 plist 파일 복사
cp com.ai-newsletter.daily.plist ~/Library/LaunchAgents/

# 권한 설정
chmod 644 ~/Library/LaunchAgents/com.ai-newsletter.daily.plist
```

### 2. launchd 등록

```bash
# launchd에 등록
launchctl load ~/Library/LaunchAgents/com.ai-newsletter.daily.plist

# 등록 확인
launchctl list | grep ai-newsletter
```

### 3. 수동 실행 테스트

```bash
# 지금 바로 실행해서 테스트
launchctl start com.ai-newsletter.daily
```

### 4. 로그 확인

```bash
# 실행 로그 확인
tail -f logs/newsletter_*.log

# launchd 로그 확인
tail -f logs/launchd.out.log
tail -f logs/launchd.err.log
```

### 5. 중지 및 제거 (필요시)

```bash
# launchd에서 제거
launchctl unload ~/Library/LaunchAgents/com.ai-newsletter.daily.plist

# plist 파일 삭제
rm ~/Library/LaunchAgents/com.ai-newsletter.daily.plist
```

---

## 방법 2: cron 사용 (Linux/macOS)

### 1. crontab 편집

```bash
crontab -e
```

### 2. 다음 라인 추가

```bash
# 매일 오전 6시에 실행
0 6 * * * /Users/Se-Hyung/Desktop/workspace/AI-Newsletter/run_newsletter.sh
```

### 3. crontab 확인

```bash
crontab -l
```

---

## 실행 시간 변경

### launchd (plist 파일 수정)

`com.ai-newsletter.daily.plist` 파일의 `StartCalendarInterval` 부분을 수정:

```xml
<key>StartCalendarInterval</key>
<dict>
    <key>Hour</key>
    <integer>6</integer>    <!-- 0-23 -->
    <key>Minute</key>
    <integer>0</integer>    <!-- 0-59 -->
</dict>
```

수정 후:
```bash
# 다시 로드
launchctl unload ~/Library/LaunchAgents/com.ai-newsletter.daily.plist
launchctl load ~/Library/LaunchAgents/com.ai-newsletter.daily.plist
```

### cron

```bash
# 분 시 일 월 요일
# 예: 오전 8시 30분
30 8 * * * /path/to/run_newsletter.sh

# 예: 오후 6시
0 18 * * * /path/to/run_newsletter.sh
```

---

## 주의사항

### 1. 환경 변수 설정

launchd는 로그인 셸의 환경 변수를 자동으로 로드하지 않습니다.

**해결 방법 A: .env 파일 사용 (권장)**

`.env` 파일에 API 키를 저장하면 자동으로 로드됩니다:

```bash
# .env 파일 생성
echo "OPENAI_API_KEY=your_key_here" > .env
```

**해결 방법 B: plist에 환경 변수 추가**

`com.ai-newsletter.daily.plist`의 `EnvironmentVariables` 섹션에 추가:

```xml
<key>EnvironmentVariables</key>
<dict>
    <key>PATH</key>
    <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>OPENAI_API_KEY</key>
    <string>your_api_key_here</string>
</dict>
```

### 2. 로그 관리

- 로그는 `logs/` 디렉토리에 저장됩니다
- 30일 이상 된 로그는 자동 삭제됩니다
- 로그 파일: `logs/newsletter_YYYYMMDD_HHMMSS.log`

### 3. 테스트

자동 실행 설정 전에 반드시 수동 실행으로 테스트:

```bash
# 수동 실행
./run_newsletter.sh

# 또는
bash run_newsletter.sh
```

---

## 트러블슈팅

### launchd가 실행되지 않을 때

1. **plist 파일 문법 확인:**
   ```bash
   plutil -lint ~/Library/LaunchAgents/com.ai-newsletter.daily.plist
   ```

2. **로그 확인:**
   ```bash
   tail -50 logs/launchd.err.log
   ```

3. **재시작:**
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.ai-newsletter.daily.plist
   launchctl load ~/Library/LaunchAgents/com.ai-newsletter.daily.plist
   ```

### 가상환경 활성화 실패

`run_newsletter.sh`의 가상환경 경로 확인:
```bash
source .venv/bin/activate
```

### API 키 오류

1. `.env` 파일 존재 확인
2. `.env` 파일 내용 확인: `OPENAI_API_KEY=sk-...`
3. 파일 권한 확인: `chmod 600 .env`

---

## 파일 구조

```
AI-Newsletter/
├── run_newsletter.sh              # 실행 스크립트
├── com.ai-newsletter.daily.plist  # launchd 설정 파일
├── logs/                          # 로그 디렉토리
│   ├── newsletter_*.log           # 실행 로그
│   ├── launchd.out.log           # launchd 표준 출력
│   └── launchd.err.log           # launchd 에러 로그
└── data/
    ├── crawled_data/
    ├── curated/
    └── newsletters/
```
