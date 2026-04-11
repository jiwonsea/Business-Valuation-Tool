"""Upload video to YouTube via Data API v3 (OAuth 2.0).

Requires one-time setup: python scripts/setup_youtube_auth.py

Token auto-refreshes via refresh_token. If re-auth is required
(e.g., Google revokes "test" app tokens), send_error_alert() is called.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOKEN_FILE = PROJECT_ROOT / "token.json"
CREDENTIALS_FILE = PROJECT_ROOT / "credentials.json"

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

_DISCLAIMER_KO = "이 영상은 AI가 자동 생성한 분석 자료이며 투자 추천이 아닙니다."


def _get_youtube_service():
    """Build authenticated YouTube API service."""
    if not TOKEN_FILE.exists():
        raise FileNotFoundError(
            "token.json not found. Run: python scripts/setup_youtube_auth.py"
        )

    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
            logger.info("YouTube token refreshed successfully.")
        except Exception as e:
            raise RuntimeError(
                f"YouTube token refresh failed — re-run setup_youtube_auth.py: {e}"
            ) from e

    if not creds.valid:
        raise RuntimeError("YouTube credentials invalid — re-run setup_youtube_auth.py")

    return build("youtube", "v3", credentials=creds)


def _build_title(summary: dict) -> str:
    """Build YouTube video title."""
    label = summary.get("label", "Weekly Report")
    return f"주간 밸류에이션 리포트 — {label}"


def _build_description(summary: dict) -> str:
    """Build YouTube video description."""
    label = summary.get("label", "Weekly Report")
    valuations = summary.get("valuations", [])
    success = [v for v in valuations if v.get("status") == "success"]

    lines = [
        f"📈 주간 밸류에이션 리포트 — {label}",
        "",
        "분석 기업:",
    ]
    for v in success:
        name = v.get("company", "")
        market = v.get("market", "")
        lines.append(f"  • {name} ({market})")

    lines.extend(
        [
            "",
            "---",
            _DISCLAIMER_KO,
            "",
            "#주식분석 #밸류에이션 #AI분석 #투자 #주간리포트",
        ]
    )
    return "\n".join(lines)


def upload_to_youtube(
    video_path: str | Path,
    summary: dict,
) -> str | None:
    """Upload video to YouTube.

    Args:
        video_path: Path to MP4 file.
        summary: Weekly summary dict (for title/description).

    Returns:
        YouTube video URL if successful, None otherwise.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        logger.error("Video file not found: %s", video_path)
        return None

    try:
        youtube = _get_youtube_service()
    except (FileNotFoundError, RuntimeError) as e:
        logger.error("YouTube auth failed: %s", e)
        return None

    title = _build_title(summary)
    description = _build_description(summary)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["주식분석", "밸류에이션", "AI분석", "투자", "주간리포트"],
            "categoryId": "22",  # People & Blogs
            "defaultLanguage": "ko",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
    )

    try:
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )
        response = request.execute()
        video_id = response.get("id", "")
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        logger.info("YouTube upload complete: %s", video_url)
        return video_url
    except Exception as e:
        logger.error("YouTube upload failed: %s", e)
        return None


def main() -> None:
    """CLI entry point for standalone testing."""
    parser = argparse.ArgumentParser(description="Upload video to YouTube")
    parser.add_argument("--video", type=str, required=True, help="Path to MP4 file")
    parser.add_argument("--summary-json", type=str, help="Path to _weekly_summary.json")
    parser.add_argument(
        "--test", action="store_true", help="Validate auth only, don't upload"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )

    if args.test:
        try:
            _get_youtube_service()
            logger.info("YouTube auth valid — ready to upload.")
        except Exception as e:
            logger.error("YouTube auth check failed: %s", e)
        return

    if args.summary_json:
        with open(args.summary_json, encoding="utf-8") as f:
            summary = json.load(f)
    else:
        summary = {"label": "Test Upload"}

    url = upload_to_youtube(args.video, summary)
    if url:
        logger.info("Published: %s", url)
    else:
        logger.error("Upload failed or skipped.")


if __name__ == "__main__":
    main()
