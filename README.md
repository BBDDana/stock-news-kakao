# 증권뉴스 카카오톡 자동화

매일 정해진 시간에 증권 뉴스를 요약해 카카오톡 "나에게 보내기"로 받아보는 자동화 프로젝트입니다.

## 기능

- 여러 RSS 소스(한국경제·연합뉴스 등)에서 뉴스를 모아 **중복 제거** 후 발송
- 관심 키워드로 **필터링** (특정 종목/테마 뉴스만 받기)
- **코스피/코스닥/다우/나스닥/S&P500/환율** 요약, 🔺🔻 이모지로 등락 한눈에 표시
- **관심종목 현재가** 요약 (종목코드 등록 시), 카테고리별 그룹 + 등락 이모지
- **카드형(list) 메시지**로 뉴스별 클릭 링크 제공 (최대 3건, 나머지는 텍스트)
- **장전/장마감 하루 2회** 발송 모드 (`--mode open` / `--mode close`)
- 네트워크 실패 시 **자동 재시도** + **로그 파일** 기록 (`logs/app.log`)
- (선택) **AI 한줄 요약** — Anthropic API 키가 있으면 오늘의 뉴스 흐름을 1~2문장으로 요약
- 매 실행마다 표/색상을 갖춘 **HTML 프리뷰 리포트**를 `reports/latest.html`에 저장 (카카오톡 텍스트보다 훨씬 보기 좋은 시각적 버전)
- (선택) **GitHub Pages 자동 배포** — 리포트를 매번 공개 URL로 발행하고, 카카오톡 메시지에 "리포트 보기" 링크 버튼을 함께 전송

## 구성

```
증권뉴스/
├── src/
│   ├── config.py         # .env 로딩
│   ├── logger.py         # 콘솔+파일 로깅
│   ├── retry.py          # 네트워크 호출 재시도
│   ├── format_utils.py   # 등락 이모지(🔺🔻) 등 메시지 가독성 포맷
│   ├── news_fetcher.py   # 다중 RSS 수집 + 중복 제거 + 키워드 필터
│   ├── market_index.py   # 지수/환율 요약
│   ├── watchlist.py      # 관심종목 시세 (watchlist.json 카테고리별 그룹 지원)
│   ├── ai_summary.py     # (선택) AI 한줄 요약
│   ├── html_report.py    # 표+색상을 갖춘 HTML 프리뷰 리포트 생성
│   ├── publish_report.py # docs/index.html 갱신 + GitHub Pages 자동 push
│   ├── kakao_auth.py     # 최초 1회: 카카오 로그인으로 토큰 발급
│   ├── kakao_sender.py   # 텍스트/카드형 전송 (토큰 자동 갱신, 실패 시 폴백)
│   └── main.py            # 전체 실행 (수집 → 요약 → 전송)
├── tokens/                 # 발급된 access/refresh 토큰 저장 (git 제외)
├── logs/                   # 실행 로그 (git 제외)
├── reports/                # HTML 프리뷰 리포트 (git 제외, latest.html이 최신본)
├── docs/                   # GitHub Pages로 배포되는 공개 리포트 (index.html, git 포함)
├── requirements.txt
├── requirements-ai.txt     # AI 요약 기능용 선택 설치
├── watchlist.json          # 관심종목 카테고리별 목록
├── .env.example
├── run_morning.bat         # 장전 브리핑 (작업 스케줄러 등록용)
└── run_close.bat           # 장마감 브리핑 (작업 스케줄러 등록용)
```

## 0. Python 설치

이 환경에는 Python이 아직 설치되어 있지 않습니다. [python.org](https://www.python.org/downloads/)에서 3.10 이상을 설치한 뒤 (설치 시 "Add python.exe to PATH" 체크) 아래 단계를 진행하세요.

## 1. 가상환경 및 패키지 설치

```bash
cd 증권뉴스
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

AI 한줄 요약 기능을 쓰려면 추가로:

```bash
pip install -r requirements-ai.txt
```

## 2. 카카오 디벨로퍼스 앱 설정

1. https://developers.kakao.com 접속 → 로그인 → [내 애플리케이션] → 앱 생성 (카테고리는 "금융" 추천)
2. [앱 > 플랫폼 키 > REST API 키] 클릭해 상세 페이지로 들어가서:
   - **REST API 키** 값을 `.env`의 `KAKAO_REST_API_KEY`에 복사
   - **클라이언트 시크릿** 코드(기본 활성화 상태)를 `.env`의 `KAKAO_CLIENT_SECRET`에 복사
   - **카카오 로그인 리다이렉트 URI**에 `http://localhost:8000/oauth` 등록 후 저장 (포트를 바꾸려면 `.env`의 `KAKAO_REDIRECT_URI`도 함께 변경)
3. [제품 설정 > 카카오 로그인 > 일반] → 사용 설정 ON
4. [제품 설정 > 카카오 로그인 > 동의항목] → **카카오톡 메시지 전송(talk_message)** 을 "선택 동의" 또는 "이용 중 동의"로 설정 (개인 개발자 앱은 "필수 동의"가 제공되지 않는 경우가 있음 — 둘 중 하나면 충분)
   - 개인 개발자 앱은 별도 심사 없이 본인 계정으로는 바로 사용 가능합니다.
5. **[앱 > 제품 링크 관리 > 웹 도메인]** → 메시지에 링크/버튼으로 쓸 도메인을 모두 등록 (최대 10개). **등록 안 된 도메인은 API가 성공(`result_code:0`)해도 링크/버튼이 조용히 사라집니다.** 최소한 아래는 등록하세요:
   - `https://<GitHub Pages 아이디>.github.io` (5-1단계에서 만들 리포트 사이트)
   - `.env`의 `RSS_URLS`에 쓰는 뉴스 도메인 (기본값 기준 `https://www.hankyung.com`, `https://www.yna.co.kr`)
   - `https://finance.naver.com` (기본 링크 폴백)

## 3. 환경변수 설정

```bash
copy .env.example .env
```

`.env`를 열어 최소한 `KAKAO_REST_API_KEY`를 입력합니다. 나머지 옵션(키워드 필터, 관심종목, AI 요약 등)은 필요에 맞게 조정하세요. 각 항목 설명은 `.env.example` 주석을 참고하세요.

**관심종목**: 프로젝트 루트의 [watchlist.json](watchlist.json)에 카테고리별로 등록되어 있습니다.

```json
{
  "반도체 및 AI": [
    {"code": "000660", "name": "SK하이닉스"},
    {"code": "005930", "name": "삼성전자"}
  ],
  "원자재, 조선": [
    {"code": "411060", "name": "ACE KRX금현물"}
  ]
}
```

종목/ETF를 추가하려면 종목코드가 필요합니다. 코드를 모르면 아래처럼 네이버 종목 검색 API로 확인할 수 있습니다 (PowerShell 예시):

```powershell
$q = [System.Uri]::EscapeDataString("찾을 종목명")
Invoke-RestMethod "https://ac.stock.naver.com/ac?q=$q&target=stock,index" | Select-Object -Expand items | Select-Object code, name
```

카테고리 없이 간단히 쓰고 싶다면 `watchlist.json`을 삭제하고 `.env`의 `WATCHLIST=005930:삼성전자,035420:NAVER` 형식을 대신 사용하면 됩니다.

**키워드 필터 예시**: `KEYWORDS=삼성전자,반도체,금리` — 제목에 하나라도 포함된 뉴스만 발송

## 4. 최초 토큰 발급 (1회만)

```bash
python -m src.kakao_auth
```

브라우저가 열리면 카카오 로그인 후 동의합니다. 성공하면 `tokens/kakao_token.json`에 access_token / refresh_token이 저장됩니다. 이후 전송 시 access_token은 자동으로 갱신됩니다.

> refresh_token도 언젠가 만료됩니다(카카오 정책에 따라 다름). 전송이 계속 실패하면 이 단계를 다시 실행하세요.

## 5. 테스트 전송

```bash
python -m src.main --mode open
```

카카오톡으로 뉴스 카드 메시지와 지수/관심종목 요약 텍스트가 도착하면 성공입니다. 문제가 생기면 `logs/app.log`를 확인하세요.

실행할 때마다 `reports/latest.html`에 표와 색상(🔺상승 빨강 / 🔻하락 파랑)을 갖춘 프리뷰 리포트도 저장됩니다. 더블클릭해서 브라우저로 열어보세요. 끄고 싶으면 `.env`에서 `SAVE_HTML_REPORT=false`.

## 5-1. (선택) GitHub Pages로 리포트를 카카오톡 링크 버튼으로 받기

카카오톡 메시지는 HTML을 렌더링하지 못하므로, 표/색상이 있는 예쁜 버전을 카카오톡 "안에서" 보려면 그 리포트가 인터넷 URL로 접속 가능해야 합니다. 이 프로젝트는 GitHub Pages에 매 실행마다 자동으로 리포트를 배포하고, 카카오톡 메시지에 "리포트 보기" 버튼을 추가하는 방식을 사용합니다.

1. GitHub 계정으로 새 저장소를 만듭니다 (Public이어야 무료 Pages 사용 가능 — 링크를 아는 사람만 볼 수 있고 검색엔 노출되지 않음).
2. [GitHub CLI](https://cli.github.com/) 설치 후 `gh auth login --web`으로 로그인, `gh auth setup-git`으로 git 인증 연결.
3. 로컬 저장소에 원격 저장소 연결 후 최초 푸시:
   ```bash
   git remote add origin https://github.com/<아이디>/<저장소>.git
   git branch -M main
   git push -u origin main
   ```
4. 저장소의 **Settings > Pages**에서 Source를 `main` 브랜치의 `/docs` 폴더로 지정 후 저장. 1~2분 후 `https://<아이디>.github.io/<저장소>/`에서 접속됩니다.
5. `.env`의 `PUBLISH_REPORT_URL`에 그 주소를 입력합니다 (끝에 `/` 포함).

이후 `python -m src.main`을 실행할 때마다 `docs/index.html`이 갱신되고 자동으로 `git commit && git push`되어 GitHub Pages가 최신 리포트로 업데이트되며, 카카오톡에 "📊 표/색상 버전으로 보기" 메시지와 **리포트 보기** 버튼이 함께 전송됩니다. 끄고 싶으면 `.env`의 `PUBLISH_REPORT_URL`을 비워두세요.

> 작업 스케줄러로 무인 실행할 때도 git push가 동작하려면, 위 `gh auth login`을 **작업을 실행할 Windows 계정**으로 한 번 로그인해 둬야 합니다 (자격 정보가 전역 git 설정에 저장됨).

## 6. 매일 자동 실행 등록 (Windows 작업 스케줄러)

장전/장마감 두 번 받고 싶다면 `run_morning.bat`, `run_close.bat`을 각각 등록합니다. 하나만 받고 싶다면 `run_morning.bat`만 등록해도 됩니다.

```bash
schtasks /create /tn "증권뉴스_장전" /tr "C:\Users\tmddu\OneDrive\Desktop\claude_P\증권뉴스\run_morning.bat" /sc daily /st 08:50
schtasks /create /tn "증권뉴스_장마감" /tr "C:\Users\tmddu\OneDrive\Desktop\claude_P\증권뉴스\run_close.bat" /sc daily /st 15:00
```

(현재 이 프로젝트는 위 시간대로 이미 등록되어 있습니다. 시간을 바꾸려면 `schtasks /change /tn "증권뉴스_장전" /st HH:MM` 형식을 사용하세요.)

또는 GUI로 등록하려면: 시작 메뉴에서 "작업 스케줄러" 실행 → [작업 만들기] → 트리거(매일, 원하는 시간) → 동작(프로그램 시작 → 해당 `.bat`의 전체 경로) → 저장 후 우클릭 "실행"으로 확인.

## 문제 해결

- **전송 실패가 반복됨**: `logs/app.log` 확인 → 토큰 만료면 `python -m src.kakao_auth` 재실행
- **일부 지수/관심종목이 요약에서 빠짐**: 해당 데이터 소스가 일시적으로 실패한 것으로, 나머지 항목은 정상 발송됩니다 (재시도 후에도 실패한 항목만 조용히 생략)
- **뉴스가 너무 많거나 적음**: `.env`의 `NEWS_COUNT` 조정
- **카드형 메시지 대신 텍스트만 받고 싶음**: `.env`에서 `USE_LIST_TEMPLATE=false`
- **"리포트 보기" 버튼이 안 옴 / GitHub Pages가 갱신 안 됨**: `logs/app.log`에서 `git push 실패` 메시지 확인 → `gh auth status`로 로그인 상태 점검, `PUBLISH_REPORT_URL`이 정확한지(끝 `/` 포함) 확인
- **메시지는 오는데 링크/버튼만 안 보임 (API는 `result_code:0`으로 성공)**: 해당 링크의 도메인이 [앱 > 제품 링크 관리 > 웹 도메인]에 등록 안 된 경우입니다. 위 2-5단계대로 도메인을 등록하세요 — 등록되지 않은 도메인의 링크는 에러 없이 조용히 생략됩니다.

## 다음 단계 (추가 확장 아이디어)

- 텔레그램/이메일 등 다른 채널 동시 지원
- 종목별 뉴스 감성분석(호재/악재) 태깅
- 주간/월간 리포트 요약본 발송
