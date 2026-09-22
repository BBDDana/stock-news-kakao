"""최초 1회 실행: 카카오 로그인으로 access_token / refresh_token을 발급받아 저장한다.

사전 준비 (카카오 디벨로퍼스 https://developers.kakao.com):
  1. 앱 생성 후 REST API 키를 .env의 KAKAO_REST_API_KEY에 입력
  2. [제품 설정 > 카카오 로그인] 활성화
  3. [카카오 로그인 > Redirect URI]에 .env의 KAKAO_REDIRECT_URI와 동일한 값 등록
     (기본값: http://localhost:8000/oauth)
  4. [카카오 로그인 > 동의항목]에서 "카카오톡 메시지 전송(talk_message)" 동의 설정
  5. python -m src.kakao_auth 실행 후 브라우저에서 로그인/동의
"""
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from src.config import (
    KAKAO_CLIENT_SECRET,
    KAKAO_REDIRECT_URI,
    KAKAO_REST_API_KEY,
    KAKAO_TOKEN_PATH,
)

AUTHORIZE_URL = "https://kauth.kakao.com/oauth/authorize"
TOKEN_URL = "https://kauth.kakao.com/oauth/token"
SCOPE = "talk_message"

_auth_code: str | None = None


class _RedirectHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _auth_code
        query = parse_qs(urlparse(self.path).query)
        _auth_code = query.get("code", [None])[0]

        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        if _auth_code:
            self.wfile.write("<h1>인증 완료. 이 창을 닫아도 됩니다.</h1>".encode("utf-8"))
        else:
            self.wfile.write("<h1>인증 실패. 콘솔을 확인하세요.</h1>".encode("utf-8"))

    def log_message(self, format, *args):
        pass  # 콘솔 출력 억제


def _wait_for_code() -> str:
    parsed = urlparse(KAKAO_REDIRECT_URI)
    port = parsed.port or 8000

    server = HTTPServer(("localhost", port), _RedirectHandler)
    print(f"[대기] {KAKAO_REDIRECT_URI} 로의 리다이렉트를 기다리는 중...")
    while _auth_code is None:
        server.handle_request()
    server.server_close()
    return _auth_code


def issue_token() -> dict:
    if not KAKAO_REST_API_KEY:
        raise SystemExit(".env 의 KAKAO_REST_API_KEY를 먼저 설정하세요.")

    query = urlencode({
        "client_id": KAKAO_REST_API_KEY,
        "redirect_uri": KAKAO_REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
    })
    authorize_url = f"{AUTHORIZE_URL}?{query}"
    print("[안내] 브라우저에서 카카오 로그인 페이지를 엽니다...")
    webbrowser.open(authorize_url)

    code = _wait_for_code()

    token_data = {
        "grant_type": "authorization_code",
        "client_id": KAKAO_REST_API_KEY,
        "redirect_uri": KAKAO_REDIRECT_URI,
        "code": code,
    }
    if KAKAO_CLIENT_SECRET:
        token_data["client_secret"] = KAKAO_CLIENT_SECRET

    response = requests.post(TOKEN_URL, data=token_data, timeout=10)
    response.raise_for_status()
    token = response.json()

    KAKAO_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    KAKAO_TOKEN_PATH.write_text(json.dumps(token, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[완료] 토큰을 저장했습니다: {KAKAO_TOKEN_PATH}")
    return token


if __name__ == "__main__":
    issue_token()
