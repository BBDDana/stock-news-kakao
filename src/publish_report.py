"""HTML 리포트를 docs/index.html로 복사하고 GitHub Pages에 자동 배포(git push)한다."""
import shutil
import subprocess

from src.config import BASE_DIR, PUBLISH_REPORT_URL
from src.logger import get_logger

logger = get_logger()

DOCS_INDEX = BASE_DIR / "docs" / "index.html"


def _run_git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def publish_report(report_path) -> str | None:
    """docs/index.html을 갱신하고 GitHub Pages로 푸시한다. 성공 시 공개 URL을 반환한다."""
    if not PUBLISH_REPORT_URL:
        return None

    DOCS_INDEX.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(report_path, DOCS_INDEX)

    _run_git("add", "docs/index.html")

    diff = _run_git("diff", "--cached", "--quiet", "--exit-code", "docs/index.html")
    if diff.returncode == 0:
        logger.info("리포트 내용이 이전과 동일해 GitHub Pages 배포를 건너뜁니다.")
        return PUBLISH_REPORT_URL

    commit = _run_git("commit", "-m", "오늘의 증권 리포트 업데이트")
    if commit.returncode != 0:
        logger.warning(f"git commit 실패: {commit.stderr.strip()}")
        return None

    push = _run_git("push")
    if push.returncode != 0:
        logger.warning(f"git push 실패, GitHub Pages 배포를 건너뜁니다: {push.stderr.strip()}")
        return None

    logger.info(f"GitHub Pages 배포 완료: {PUBLISH_REPORT_URL}")
    return PUBLISH_REPORT_URL
