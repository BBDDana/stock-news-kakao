"""로컬 설정 대시보드. `python -m src.dashboard` 로 실행하면 브라우저가 자동으로 열린다.

.env / watchlist.json / 작업 스케줄러 발송 시간을 웹 UI에서 편집하고 저장할 수 있다.
외부에 노출하지 않고 127.0.0.1(로컬)에서만 서비스한다.
"""
import json
import re
import subprocess
import threading
import webbrowser

from dotenv import set_key
from flask import Flask, jsonify, request

from src.config import BASE_DIR, LOG_PATH, WATCHLIST_PATH

ENV_PATH = BASE_DIR / ".env"
TASK_NAMES = {"open": "증권뉴스_장전", "close": "증권뉴스_장마감"}

app = Flask(__name__)

CONFIG_FIELDS = [
    # (key, type, default) — type: "str" | "int" | "float" | "bool"
    ("RSS_URLS", "list", ""),
    ("NEWS_COUNT", "int", "5"),
    ("KEYWORDS", "list", ""),
    ("DEDUP_SIMILARITY", "float", "0.6"),
    ("SEND_MARKET_SUMMARY", "bool", "true"),
    ("USE_LIST_TEMPLATE", "bool", "true"),
    ("SAVE_HTML_REPORT", "bool", "true"),
    ("PUBLISH_REPORT_URL", "str", ""),
    ("USE_AI_SUMMARY", "bool", "false"),
    ("ANTHROPIC_API_KEY", "str", ""),
    ("AI_SUMMARY_MODEL", "str", "claude-haiku-4-5-20251001"),
]


def _read_env() -> dict:
    values = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def _get_config_state() -> dict:
    raw = _read_env()
    state = {}
    for key, ftype, default in CONFIG_FIELDS:
        value = raw.get(key, default)
        if ftype == "bool":
            state[key] = value.lower() == "true"
        elif ftype == "list":
            state[key] = [v.strip() for v in value.split(",") if v.strip()]
        else:
            state[key] = value
    return state


def _save_config(payload: dict) -> None:
    for key, ftype, _default in CONFIG_FIELDS:
        if key not in payload:
            continue
        value = payload[key]
        if ftype == "bool":
            serialized = "true" if value else "false"
        elif ftype == "list":
            serialized = ",".join(v.strip() for v in value if v.strip())
        else:
            serialized = str(value)
        set_key(str(ENV_PATH), key, serialized, quote_mode="never")


def _get_watchlist() -> dict:
    if WATCHLIST_PATH.exists():
        return json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))
    return {}


def _save_watchlist(groups: dict) -> None:
    WATCHLIST_PATH.write_text(json.dumps(groups, ensure_ascii=False, indent=2), encoding="utf-8")


def _to_24h(raw: str | None) -> str | None:
    """schtasks의 로케일별 시간 표기(오전/오후 8:50:00, 8:50:00 AM 등)를 HH:MM(24시간제)으로 변환한다."""
    if not raw:
        return None
    is_pm = "오후" in raw or re.search(r"\bPM\b", raw, re.I)
    is_am = "오전" in raw or re.search(r"\bAM\b", raw, re.I)
    m = re.search(r"(\d{1,2}):(\d{2})", raw)
    if not m:
        return None
    hour, minute = int(m.group(1)), m.group(2)
    if is_pm and hour != 12:
        hour += 12
    if is_am and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute}"


def _query_schedule() -> dict:
    schedule = {}
    for mode, task_name in TASK_NAMES.items():
        try:
            result = subprocess.run(
                ["schtasks", "/query", "/tn", task_name, "/v", "/fo", "list"],
                capture_output=True, text=True, encoding="utf-8", errors="ignore",
            )
            time_value = None
            for line in result.stdout.splitlines():
                if line.strip().startswith("Start Time:") or line.strip().startswith("시작 시간:"):
                    time_value = _to_24h(line.split(":", 1)[1].strip())
            schedule[mode] = {"task_name": task_name, "exists": result.returncode == 0, "start_time": time_value}
        except Exception:
            schedule[mode] = {"task_name": task_name, "exists": False, "start_time": None}
    return schedule


def _set_schedule_time(mode: str, hhmm: str) -> tuple[bool, str]:
    task_name = TASK_NAMES.get(mode)
    if not task_name:
        return False, "알 수 없는 모드"
    result = subprocess.run(
        ["schtasks", "/change", "/tn", task_name, "/st", f"{hhmm}:00"],
        capture_output=True, text=True, encoding="utf-8", errors="ignore",
    )
    return result.returncode == 0, (result.stdout or result.stderr).strip()


@app.get("/")
def index():
    return DASHBOARD_HTML


@app.get("/api/state")
def api_state():
    return jsonify({
        "config": _get_config_state(),
        "watchlist": _get_watchlist(),
        "schedule": _query_schedule(),
    })


@app.post("/api/config")
def api_save_config():
    _save_config(request.get_json(force=True))
    return jsonify({"ok": True, "config": _get_config_state()})


@app.post("/api/watchlist")
def api_save_watchlist():
    _save_watchlist(request.get_json(force=True))
    return jsonify({"ok": True, "watchlist": _get_watchlist()})


@app.post("/api/schedule")
def api_save_schedule():
    payload = request.get_json(force=True)
    results = {}
    for mode, hhmm in payload.items():
        if not hhmm:
            continue
        ok, message = _set_schedule_time(mode, hhmm)
        results[mode] = {"ok": ok, "message": message}
    return jsonify({"results": results, "schedule": _query_schedule()})


@app.post("/api/test-send")
def api_test_send():
    mode = request.get_json(force=True).get("mode", "open")
    result = subprocess.run(
        ["python", "-m", "src.main", "--mode", mode],
        cwd=BASE_DIR, capture_output=True, text=True, encoding="utf-8", errors="ignore",
    )
    return jsonify({"ok": result.returncode == 0, "output": (result.stdout + result.stderr)[-4000:]})


@app.get("/api/logs")
def api_logs():
    if not LOG_PATH.exists():
        return jsonify({"lines": []})
    lines = LOG_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()[-100:]
    return jsonify({"lines": lines})


DASHBOARD_HTML = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>증권기자 설정</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Gowun+Dodum&family=IBM+Plex+Sans+KR:wght@400;500;600&display=swap">
<style>
:root {
  --paper: #f6f3ec; --surface: #ffffff; --ink: #211f1c; --muted: #6b6459;
  --line: #e4dfd3; --accent: #b8862f; --accent-deep: #1d2a44;
  --up: #c0392b; --up-bg: #fbeae7; --down: #2a5ca8; --down-bg: #e9f0fa;
  --ok: #2e7d46; --ok-bg: #e7f4ea;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--paper); color: var(--ink);
  font-family: 'IBM Plex Sans KR', 'Noto Sans KR', -apple-system, sans-serif;
  padding: 24px 16px 64px;
}
.wrap { max-width: 760px; margin: 0 auto; }
h1, h2, h3 { font-family: 'Gowun Dodum', 'Noto Sans KR', sans-serif; margin: 0; }
.masthead {
  background: var(--accent-deep); color: #f4efe3; border-radius: 14px;
  padding: 20px 24px; margin-bottom: 20px;
}
.masthead h1 { font-size: 1.4rem; }
.masthead p { margin: 4px 0 0; color: var(--accent); font-size: 0.9rem; }
.card {
  background: var(--surface); border: 1px solid var(--line); border-radius: 14px;
  padding: 20px 22px; margin-bottom: 16px;
}
.card h2 { font-size: 1.05rem; margin-bottom: 4px; }
.card .desc { color: var(--muted); font-size: 0.85rem; margin: 0 0 14px; }
.field { margin-bottom: 14px; }
.field label { display: block; font-size: 0.85rem; color: var(--muted); margin-bottom: 4px; }
.field input[type="text"], .field input[type="number"], .field input[type="password"], .field input[type="time"] {
  width: 100%; padding: 8px 10px; border: 1px solid var(--line); border-radius: 8px;
  font-size: 0.95rem; background: var(--paper); color: var(--ink); font-family: inherit;
}
.row { display: flex; gap: 12px; flex-wrap: wrap; }
.row .field { flex: 1; min-width: 160px; }
.toggle-row { display: flex; align-items: center; justify-content: space-between; padding: 6px 0; }
.toggle-row .label { font-size: 0.92rem; }
.toggle-row .sub { color: var(--muted); font-size: 0.78rem; }
.switch { position: relative; width: 42px; height: 24px; flex: none; }
.switch input { opacity: 0; width: 0; height: 0; }
.slider { position: absolute; inset: 0; background: var(--line); border-radius: 999px; cursor: pointer; transition: .15s; }
.slider::before { content: ""; position: absolute; width: 18px; height: 18px; left: 3px; top: 3px; background: white; border-radius: 50%; transition: .15s; }
input:checked + .slider { background: var(--accent-deep); }
input:checked + .slider::before { transform: translateX(18px); }
.group { border: 1px solid var(--line); border-radius: 10px; padding: 12px; margin-bottom: 12px; }
.group-title { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; gap: 8px; }
.group-title input { flex: 1; font-weight: 600; border: none; background: transparent; font-size: 0.95rem; padding: 4px; }
.stock-row { display: flex; gap: 8px; margin-bottom: 6px; align-items: center; }
.stock-row input { padding: 6px 8px; border: 1px solid var(--line); border-radius: 6px; background: var(--paper); }
.stock-row input.code { width: 90px; }
.stock-row input.name { flex: 1; }
button {
  font-family: inherit; border: none; border-radius: 8px; padding: 8px 14px;
  font-size: 0.88rem; cursor: pointer; background: var(--line); color: var(--ink);
}
button.primary { background: var(--accent-deep); color: #f4efe3; }
button.ghost { background: transparent; border: 1px solid var(--line); }
button.danger { background: var(--up-bg); color: var(--up); }
button:hover { filter: brightness(1.05); }
.actions { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 4px; }
.toast {
  position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
  background: var(--ok-bg); color: var(--ok); padding: 10px 18px; border-radius: 999px;
  font-size: 0.88rem; opacity: 0; transition: opacity .2s; pointer-events: none;
}
.toast.show { opacity: 1; }
.toast.error { background: var(--up-bg); color: var(--up); }
pre.logs {
  background: var(--accent-deep); color: #d9d3c4; padding: 12px; border-radius: 8px;
  font-size: 0.78rem; max-height: 260px; overflow: auto; white-space: pre-wrap; word-break: break-all;
}
.schedule-row { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
.schedule-row .name { flex: 1; font-size: 0.92rem; }
.schedule-row .status { font-size: 0.78rem; color: var(--muted); }
</style>
</head>
<body>
<div class="wrap">
  <div class="masthead">
    <h1>증권기자 설정</h1>
    <p>뉴스·관심종목·발송 스케줄을 여기서 관리하세요</p>
  </div>

  <div class="card">
    <h2>발송 스케줄</h2>
    <p class="desc">Windows 작업 스케줄러에 등록된 시간을 바로 조회/변경합니다.</p>
    <div id="schedule-list"></div>
    <div class="actions">
      <button class="primary" onclick="saveSchedule()">스케줄 저장</button>
    </div>
  </div>

  <div class="card">
    <h2>뉴스 설정</h2>
    <div class="field">
      <label>RSS 소스 (쉼표로 구분)</label>
      <input type="text" id="cfg-RSS_URLS">
    </div>
    <div class="row">
      <div class="field">
        <label>뉴스 개수</label>
        <input type="number" id="cfg-NEWS_COUNT" min="1" max="20">
      </div>
      <div class="field">
        <label>중복 판단 유사도 (0~1)</label>
        <input type="number" id="cfg-DEDUP_SIMILARITY" min="0" max="1" step="0.05">
      </div>
    </div>
    <div class="field">
      <label>우선 배치 키워드 (쉼표로 구분, 상단에 우선 노출)</label>
      <input type="text" id="cfg-KEYWORDS">
    </div>
  </div>

  <div class="card">
    <h2>메시지 옵션</h2>
    <div class="toggle-row">
      <div><div class="label">시장 지표(지수/환율) 포함</div></div>
      <label class="switch"><input type="checkbox" id="cfg-SEND_MARKET_SUMMARY"><span class="slider"></span></label>
    </div>
    <div class="toggle-row">
      <div><div class="label">뉴스 카드형(list) 템플릿 사용</div><div class="sub">끄면 전부 텍스트로 전송</div></div>
      <label class="switch"><input type="checkbox" id="cfg-USE_LIST_TEMPLATE"><span class="slider"></span></label>
    </div>
    <div class="toggle-row">
      <div><div class="label">HTML 리포트 저장</div><div class="sub">reports/latest.html</div></div>
      <label class="switch"><input type="checkbox" id="cfg-SAVE_HTML_REPORT"><span class="slider"></span></label>
    </div>
    <div class="field" style="margin-top:12px">
      <label>GitHub Pages 리포트 URL (비우면 "리포트 보기" 버튼 전송 안 함)</label>
      <input type="text" id="cfg-PUBLISH_REPORT_URL">
    </div>
  </div>

  <div class="card">
    <h2>AI 한줄 요약 (선택)</h2>
    <div class="toggle-row">
      <div><div class="label">AI 요약 사용</div><div class="sub">requirements-ai.txt 설치 필요</div></div>
      <label class="switch"><input type="checkbox" id="cfg-USE_AI_SUMMARY"><span class="slider"></span></label>
    </div>
    <div class="field" style="margin-top:10px">
      <label>Anthropic API 키</label>
      <input type="password" id="cfg-ANTHROPIC_API_KEY" placeholder="변경할 때만 입력">
    </div>
    <div class="field">
      <label>모델</label>
      <input type="text" id="cfg-AI_SUMMARY_MODEL">
    </div>
  </div>

  <div class="card">
    <h2>관심종목</h2>
    <p class="desc">카테고리별로 종목을 관리합니다. 종목코드를 모르면 네이버 종목 검색을 참고하세요.</p>
    <div id="watchlist-groups"></div>
    <div class="actions">
      <button class="ghost" onclick="addGroup()">+ 카테고리 추가</button>
      <button class="primary" onclick="saveWatchlist()">관심종목 저장</button>
    </div>
  </div>

  <div class="card">
    <h2>저장 및 테스트</h2>
    <div class="actions">
      <button class="primary" onclick="saveConfig()">설정 저장</button>
      <button onclick="testSend('open')">장전 테스트 발송</button>
      <button onclick="testSend('close')">장마감 테스트 발송</button>
      <button class="ghost" onclick="loadLogs()">로그 새로고침</button>
    </div>
    <pre class="logs" id="logs" style="margin-top:14px;"></pre>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
let state = { config: {}, watchlist: {}, schedule: {} };

function toast(msg, isError) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'toast show' + (isError ? ' error' : '');
  setTimeout(() => { el.className = 'toast'; }, 2500);
}

async function loadState() {
  const res = await fetch('/api/state');
  state = await res.json();
  renderConfig();
  renderSchedule();
  renderWatchlist();
}

function renderConfig() {
  const c = state.config;
  document.getElementById('cfg-RSS_URLS').value = (c.RSS_URLS || []).join(', ');
  document.getElementById('cfg-NEWS_COUNT').value = c.NEWS_COUNT;
  document.getElementById('cfg-DEDUP_SIMILARITY').value = c.DEDUP_SIMILARITY;
  document.getElementById('cfg-KEYWORDS').value = (c.KEYWORDS || []).join(', ');
  document.getElementById('cfg-SEND_MARKET_SUMMARY').checked = !!c.SEND_MARKET_SUMMARY;
  document.getElementById('cfg-USE_LIST_TEMPLATE').checked = !!c.USE_LIST_TEMPLATE;
  document.getElementById('cfg-SAVE_HTML_REPORT').checked = !!c.SAVE_HTML_REPORT;
  document.getElementById('cfg-PUBLISH_REPORT_URL').value = c.PUBLISH_REPORT_URL || '';
  document.getElementById('cfg-USE_AI_SUMMARY').checked = !!c.USE_AI_SUMMARY;
  document.getElementById('cfg-AI_SUMMARY_MODEL').value = c.AI_SUMMARY_MODEL || '';
  document.getElementById('cfg-ANTHROPIC_API_KEY').value = '';
}

function renderSchedule() {
  const box = document.getElementById('schedule-list');
  box.innerHTML = '';
  for (const [mode, info] of Object.entries(state.schedule)) {
    const label = mode === 'open' ? '장전 브리핑' : '장마감 브리핑';
    const hhmm = (info.start_time || '').slice(0, 5);
    const row = document.createElement('div');
    row.className = 'schedule-row';
    row.innerHTML = `
      <div class="name">${label} <span class="status">(${info.task_name}${info.exists ? '' : ' · 미등록'})</span></div>
      <input type="time" id="sched-${mode}" value="${hhmm}">
    `;
    box.appendChild(row);
  }
}

function renderWatchlist() {
  const box = document.getElementById('watchlist-groups');
  box.innerHTML = '';
  for (const [groupName, stocks] of Object.entries(state.watchlist)) {
    box.appendChild(buildGroupEl(groupName, stocks));
  }
}

function buildGroupEl(groupName, stocks) {
  const div = document.createElement('div');
  div.className = 'group';
  const title = document.createElement('div');
  title.className = 'group-title';
  title.innerHTML = `
    <input type="text" class="group-name" value="${groupName}">
    <button class="ghost" onclick="this.closest('.group').remove()">카테고리 삭제</button>
  `;
  div.appendChild(title);

  const rowsBox = document.createElement('div');
  rowsBox.className = 'stock-rows';
  (stocks || []).forEach(s => rowsBox.appendChild(buildStockRow(s.code, s.name)));
  div.appendChild(rowsBox);

  const addBtn = document.createElement('button');
  addBtn.className = 'ghost';
  addBtn.textContent = '+ 종목 추가';
  addBtn.onclick = () => rowsBox.appendChild(buildStockRow('', ''));
  div.appendChild(addBtn);

  return div;
}

function buildStockRow(code, name) {
  const row = document.createElement('div');
  row.className = 'stock-row';
  row.innerHTML = `
    <input type="text" class="code" placeholder="종목코드" value="${code}">
    <input type="text" class="name" placeholder="종목명" value="${name}">
    <button class="danger" onclick="this.closest('.stock-row').remove()">삭제</button>
  `;
  return row;
}

function addGroup() {
  document.getElementById('watchlist-groups').appendChild(buildGroupEl('새 카테고리', []));
}

async function saveConfig() {
  const payload = {
    RSS_URLS: document.getElementById('cfg-RSS_URLS').value.split(',').map(s => s.trim()).filter(Boolean),
    NEWS_COUNT: parseInt(document.getElementById('cfg-NEWS_COUNT').value || '5', 10),
    DEDUP_SIMILARITY: parseFloat(document.getElementById('cfg-DEDUP_SIMILARITY').value || '0.6'),
    KEYWORDS: document.getElementById('cfg-KEYWORDS').value.split(',').map(s => s.trim()).filter(Boolean),
    SEND_MARKET_SUMMARY: document.getElementById('cfg-SEND_MARKET_SUMMARY').checked,
    USE_LIST_TEMPLATE: document.getElementById('cfg-USE_LIST_TEMPLATE').checked,
    SAVE_HTML_REPORT: document.getElementById('cfg-SAVE_HTML_REPORT').checked,
    PUBLISH_REPORT_URL: document.getElementById('cfg-PUBLISH_REPORT_URL').value.trim(),
    USE_AI_SUMMARY: document.getElementById('cfg-USE_AI_SUMMARY').checked,
    AI_SUMMARY_MODEL: document.getElementById('cfg-AI_SUMMARY_MODEL').value.trim(),
  };
  const apiKey = document.getElementById('cfg-ANTHROPIC_API_KEY').value.trim();
  if (apiKey) payload.ANTHROPIC_API_KEY = apiKey;

  const res = await fetch('/api/config', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) });
  const data = await res.json();
  if (data.ok) { toast('설정을 저장했습니다.'); state.config = data.config; } else { toast('저장 실패', true); }
}

async function saveWatchlist() {
  const groups = {};
  document.querySelectorAll('#watchlist-groups .group').forEach(g => {
    const name = g.querySelector('.group-name').value.trim();
    if (!name) return;
    const stocks = [];
    g.querySelectorAll('.stock-row').forEach(r => {
      const code = r.querySelector('.code').value.trim();
      const sname = r.querySelector('.name').value.trim();
      if (code && sname) stocks.push({ code, name: sname });
    });
    groups[name] = stocks;
  });
  const res = await fetch('/api/watchlist', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(groups) });
  const data = await res.json();
  if (data.ok) { toast('관심종목을 저장했습니다.'); state.watchlist = data.watchlist; } else { toast('저장 실패', true); }
}

async function saveSchedule() {
  const payload = {};
  document.querySelectorAll('[id^="sched-"]').forEach(el => {
    const mode = el.id.replace('sched-', '');
    if (el.value) payload[mode] = el.value;
  });
  const res = await fetch('/api/schedule', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) });
  const data = await res.json();
  const failed = Object.values(data.results || {}).some(r => !r.ok);
  toast(failed ? '일부 스케줄 저장 실패' : '스케줄을 저장했습니다.', failed);
  state.schedule = data.schedule;
  renderSchedule();
}

async function testSend(mode) {
  toast('발송 중... (몇 초 걸릴 수 있어요)');
  const res = await fetch('/api/test-send', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ mode }) });
  const data = await res.json();
  toast(data.ok ? '테스트 발송 완료' : '발송 실패, 로그 확인', !data.ok);
  document.getElementById('logs').textContent = data.output;
}

async function loadLogs() {
  const res = await fetch('/api/logs');
  const data = await res.json();
  document.getElementById('logs').textContent = data.lines.join('\n');
}

loadState();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5050")).start()
    app.run(host="127.0.0.1", port=5050, debug=False)
