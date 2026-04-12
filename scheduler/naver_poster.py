"""Post weekly valuation report to Naver Blog via Selenium.

Posts both KR and US market companies in Korean language.
Uses Chrome with persistent profile to avoid CAPTCHA on repeated runs.

Env vars:
  NAVER_ID  — Naver account ID (never logged)
  NAVER_PW  — Naver account password (never logged)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)

_LOGIN_URL = "https://nid.naver.com/nidlogin.login"
_WRITE_URL_TMPL = "https://blog.naver.com/{blog_id}/postwrite"
_PROFILE_DIR = Path.home() / ".naver_poster_chrome"

# Wait timeouts (seconds)
_SHORT = 5
_LONG = 20

_DISCLAIMER_KR = (
    "\n\n---\n\n"
    "이 리포트는 AI 기반 밸류에이션 파이프라인이 자동 생성한 분석 자료이며, "
    "투자 조언이 아닙니다. 투자 의사결정 시 반드시 자체적인 실사를 진행하세요."
)


# ── Credentials ──────────────────────────────────────────────────────────────


def _get_credentials() -> tuple[str, str]:
    """Return (naver_id, naver_pw) from environment. Never log these values."""
    return os.getenv("NAVER_ID", ""), os.getenv("NAVER_PW", "")


# ── Content building ──────────────────────────────────────────────────────────


def _safe_url(url: str) -> str:
    """Return url only if scheme is http/https; empty string otherwise."""
    if not url:
        return ""
    return url if urlparse(url).scheme in ("http", "https") else ""


# ── Logo helpers ─────────────────────────────────────────────────────────────


def _download_logo(domain: str) -> str:
    """Download company logo PNG from Clearbit to a temp file.

    Args:
        domain: Root domain extracted by discovery AI (e.g. "samsung.com").
            Empty string or None skips the download immediately.

    Returns:
        Absolute path to the downloaded temp file on success, empty string
        otherwise. Caller is responsible for deleting the file.
    """
    if not domain:
        return ""
    url = f"https://logo.clearbit.com/{domain}"
    try:
        resp = requests.get(url, timeout=5)
        content_type = resp.headers.get("content-type", "")
        if resp.ok and content_type.startswith("image/"):
            suffix = ".png" if "png" in content_type else ".jpg"
            fd, tmp_path = tempfile.mkstemp(suffix=suffix)
            os.write(fd, resp.content)
            os.close(fd)
            logger.debug("Logo downloaded domain=%s → %s", domain, tmp_path)
            return tmp_path
    except Exception as e:
        logger.debug("Logo download failed domain=%s: %s", domain, e)
    return ""


def _insert_logo_se3(driver: webdriver.Chrome, logo_path: str) -> bool:
    """Upload a logo image into SE3 at the current cursor position.

    Diagnostic result (2026-04-12):
      - button.se-image-toolbar-button exists and is clickable.
      - Clicking it does NOT reveal a new panel with input[type='file'].
      - SE3 keeps input[type='file'] hidden (display:none) in the DOM at all times.
        Selenium send_keys() works on hidden file inputs without making them visible.

    Flow (revised):
      1. Find hidden input[type='file'] via JavaScript (no visibility filter).
      2. send_keys(abs_path) — Selenium bypasses hidden state for file inputs.
      3. Wait for SE3 to render the resulting image component.

    Returns True on success, False if any step fails (best-effort, non-fatal).
    """
    abs_path = str(Path(logo_path).resolve())

    # Step 1 — locate hidden file input via JS (offsetParent filter would miss it)
    try:
        file_input = driver.execute_script(
            "return document.querySelector('input[type=\"file\"]');"
        )
        if not file_input:
            logger.warning("SE3: no input[type='file'] in DOM — skipping logo insert.")
            return False
    except WebDriverException as e:
        logger.warning("SE3 file input JS query failed: %s — skipping logo insert.", e)
        return False

    # Step 2 — send file path; Selenium handles hidden inputs natively
    try:
        file_input.send_keys(abs_path)
        logger.debug("Logo file sent to hidden input: %s", abs_path)
    except WebDriverException as e:
        logger.warning("SE3 send_keys to file input failed: %s — skipping logo insert.", e)
        return False

    # Step 3 — wait for SE3 to render the uploaded image component
    try:
        WebDriverWait(driver, _LONG).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "div.se-component.se-image, div.se-imageContainer")
            )
        )
        logger.debug("SE3 image component detected after upload.")
    except TimeoutException:
        logger.debug("SE3 image component timeout — upload may still be processing.")

    time.sleep(0.5)
    return True


def _shorten_url(url: str) -> str:
    """Shorten a long URL via TinyURL (no API key required).

    Falls back to the original URL on any network/timeout error.
    """
    if not url:
        return url
    try:
        resp = requests.get(
            "https://tinyurl.com/api-create.php",
            params={"url": url},
            timeout=5,
        )
        if resp.ok and resp.text.startswith("http"):
            return resp.text.strip()
    except Exception:
        pass
    return url


def _strip_dangerous_tags(text: str) -> str:
    """Remove script/iframe/object/embed/form tags (injection defence)."""
    text = re.sub(
        r"<(script|iframe|object|embed|form)[^>]*>.*?</\1>",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return re.sub(
        r"<(script|iframe|object|embed|form)[^>]*/?>",
        "",
        text,
        flags=re.IGNORECASE,
    )


def _build_company_text(
    v: dict,
    company_news: dict[str, list[dict]],
) -> str:
    """Build plain-text block for one company valuation entry."""
    name = v.get("company", "")
    market = v.get("market", "")
    cap = v.get("market_cap_usd")

    if cap is not None and cap >= 1_000_000_000_000:
        cap_str = f"${cap / 1_000_000_000_000:.1f}T"
    elif cap is not None and cap >= 1_000_000_000:
        cap_str = f"${cap / 1_000_000_000:.1f}B"
    elif cap is not None:
        cap_str = f"${cap / 1_000_000:,.0f}M"
    else:
        cap_str = "N/A"

    reason = v.get("reason", "")
    summary_md = v.get("summary_md", "")
    raw_url = _safe_url(v.get("download_url", ""))

    lines: list[str] = []
    lines.append(f"▶ {name} ({market} · {cap_str})")

    if reason:
        lines.append(f"  선정 이유: {_strip_dangerous_tags(reason)}")

    if summary_md:
        md_lines = summary_md.strip().split("\n")[:10]
        lines.extend(f"  {ln}" for ln in md_lines if ln.strip())

    news_items = company_news.get(name, [])
    if news_items:
        lines.append("  [관련 뉴스]")
        for ni in news_items:
            n_title = _strip_dangerous_tags(ni.get("title", ""))
            n_url = _safe_url(ni.get("url", ""))
            if n_title and n_url:
                lines.append(f"  - {n_title}")
                lines.append(f"    {n_url}")

    if raw_url:
        short_url = _shorten_url(raw_url)
        lines.append(f"  Excel 다운로드: {short_url}")

    return "\n".join(lines)


# Section type constants
_SEC_TEXT = "text"
_SEC_COMPANY = "company"


def build_blog_sections(summary: dict) -> tuple[str, list[dict]]:
    """Build (title, sections) for structured Naver Blog posting.

    Each section is one of:
      {"type": "text",    "content": "..."}
      {"type": "company", "name": "...", "content": "..."}

    Company sections carry the company name so the caller can attempt
    logo insertion before injecting the text content.

    Args:
        summary: The full _weekly_summary.json content.

    Returns:
        (title, sections)
    """
    label = summary.get("label", "")
    markets = summary.get("markets", [])
    status = summary.get("status_summary", {})
    valuations = summary.get("valuations", [])
    discoveries = summary.get("discoveries", [])

    title = f"주간 밸류에이션 리포트 — {label}"

    # Build per-company lookups from discovery data (name → news, name → domain)
    company_news: dict[str, list[dict]] = {}
    company_domains: dict[str, str] = {}
    for d in discoveries:
        for co in d.get("companies", []):
            name = co.get("name", "")
            if not name:
                continue
            news_items = co.get("top_news", [])
            if news_items:
                company_news[name] = news_items
            domain = co.get("domain") or ""
            if domain:
                company_domains[name] = domain

    sections: list[dict] = []

    # ── 개요 ──
    header_lines = [
        f"■ 주간 밸류에이션 리포트 — {label}\n",
        f"대상 시장: {', '.join(markets)} | "
        f"분석 기업: {status.get('success', 0)}개 성공 / {status.get('total', 0)}개 대상\n",
    ]
    if discoveries:
        header_lines.append("\n■ 이번 주 발굴 기업\n")
        for d in discoveries:
            mkt = d.get("market", "")
            news_count = d.get("news_count", 0)
            cos = d.get("companies", [])
            co_names = ", ".join(c.get("name", "") for c in cos[:5])
            header_lines.append(f"[{mkt}] 뉴스 {news_count}건 → 후보 기업: {co_names}")

    sections.append({"type": _SEC_TEXT, "content": "\n".join(header_lines)})

    # ── 기업별 분석 ──
    success_valuations = [v for v in valuations if v.get("status") == "success"]
    if success_valuations:
        sections.append({"type": _SEC_TEXT, "content": "\n\n■ 기업별 밸류에이션 요약\n"})
        for v in success_valuations:
            name = v.get("company", "")
            sections.append(
                {
                    "type": _SEC_COMPANY,
                    "name": name,
                    # domain from discovery AI — used for Clearbit logo download
                    "domain": company_domains.get(name, ""),
                    "content": _build_company_text(v, company_news),
                }
            )

    sections.append({"type": _SEC_TEXT, "content": _DISCLAIMER_KR})

    return title, sections


def build_blog_content(summary: dict) -> tuple[str, str]:
    """Build (title, plain_text_body) for Naver Blog post (Korean).

    Convenience wrapper around build_blog_sections for callers that only
    need a single text body (e.g. tests, dry-run CLI).

    Args:
        summary: The full _weekly_summary.json content.

    Returns:
        (title, body) where body is plain text suitable for SmartEditor.
    """
    title, sections = build_blog_sections(summary)
    body = "\n\n".join(s["content"] for s in sections)
    return title, body


# ── Chrome driver ─────────────────────────────────────────────────────────────


def _build_driver(headless: bool = False) -> webdriver.Chrome:
    """Create Chrome WebDriver with persistent profile for CAPTCHA avoidance.

    Args:
        headless: Run Chrome in headless mode.
            Note: Naver may block headless user-agents; False is safer.
    """
    _PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    opts = Options()
    opts.add_argument(f"--user-data-dir={_PROFILE_DIR}")
    opts.add_argument("--profile-directory=Default")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    if headless:
        opts.add_argument("--headless=new")

    driver = webdriver.Chrome(options=opts)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


# ── Login ─────────────────────────────────────────────────────────────────────


def _is_logged_in(driver: webdriver.Chrome) -> bool:
    """Check if both Naver session cookies are present."""
    cookies = {c["name"] for c in driver.get_cookies()}
    return {"NID_AUT", "NID_SES"}.issubset(cookies)


def _login(
    driver: webdriver.Chrome,
    wait: WebDriverWait,
    naver_id: str,
    naver_pw: str,
) -> bool:
    """Perform Naver login. Returns True on success.

    Credential values are never written to logs.
    """
    try:
        driver.get(_LOGIN_URL)
        wait.until(EC.presence_of_element_located((By.ID, "id")))

        id_field = driver.find_element(By.ID, "id")
        pw_field = driver.find_element(By.ID, "pw")

        # Set values via JavaScript to avoid keystroke detection
        driver.execute_script("arguments[0].value = arguments[1];", id_field, naver_id)
        driver.execute_script("arguments[0].value = arguments[1];", pw_field, naver_pw)
        driver.execute_script(
            "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));",
            id_field,
        )
        driver.execute_script(
            "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));",
            pw_field,
        )

        login_btn = driver.find_element(By.ID, "log.login")
        login_btn.click()

        # Wait for both session cookies to be issued (async after redirect)
        try:
            WebDriverWait(driver, _LONG).until(
                lambda d: {"NID_AUT", "NID_SES"}.issubset(
                    {c["name"] for c in d.get_cookies()}
                )
            )
            logger.info("Naver login successful.")
            return True
        except TimeoutException:
            logger.warning("Naver login: session cookies not issued within timeout.")
            return False

    except (TimeoutException, NoSuchElementException) as e:
        logger.error("Naver login failed: %s", e)
        return False


# ── Blog posting ──────────────────────────────────────────────────────────────


def _dismiss_draft_dialog(driver: webdriver.Chrome) -> None:
    """Dismiss '작성 중인 글이 있습니다' popup if it appears.

    Clicks 확인 to continue into the editor (draft content is overwritten later).
    Uses a short timeout so a missing dialog is a silent no-op.
    """
    try:
        btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.se-popup-button-confirm"))
        )
        btn.click()
        logger.debug("Draft resume dialog dismissed.")
        time.sleep(0.5)
    except TimeoutException:
        pass  # No dialog — fresh write page, continue normally


def _wait_for_editor(driver: webdriver.Chrome, wait: WebDriverWait) -> bool:
    """Wait for SmartEditor 3 to finish loading in the top-level DOM.

    Naver SE3 renders directly in the page (no #mainFrame wrapper).
    Key containers: div.se-wrap, div.se-body, div.se-component.
    """
    selectors = [
        (By.CSS_SELECTOR, "div.se-wrap"),
        (By.CSS_SELECTOR, "div.se-body"),
        (By.CSS_SELECTOR, "div.se-component"),
        (By.CSS_SELECTOR, "div[class*='se-body']"),
        (By.CSS_SELECTOR, "div.se2_inputarea"),
    ]
    for by, sel in selectors:
        try:
            wait.until(EC.presence_of_element_located((by, sel)))
            logger.debug("Editor detected with selector: %s", sel)
            return True
        except TimeoutException:
            continue
    logger.warning("SmartEditor container not found within timeout.")
    return False


def _set_title(driver: webdriver.Chrome, wait: WebDriverWait, title: str) -> bool:
    """Fill in the post title. Returns True on success.

    SE3 has ONE div[contenteditable='true'] covering the whole canvas.
    The title lives inside div.se-documentTitle p — clicking it moves the
    cursor there, then ActionChains can type normally.
    """
    selectors = [
        (By.CSS_SELECTOR, "div.se-documentTitle p"),
        (By.CSS_SELECTOR, "div.se-documentTitle"),
        (By.CSS_SELECTOR, "div.se-component.se-documentTitle"),
    ]
    for by, sel in selectors:
        try:
            elem = driver.find_element(by, sel)
            driver.execute_script("arguments[0].scrollIntoView(true);", elem)
            elem.click()
            time.sleep(0.3)
            # Ctrl+A selects within current component in SE3
            ActionChains(driver).key_down(Keys.CONTROL).send_keys("a").key_up(
                Keys.CONTROL
            ).perform()
            time.sleep(0.1)
            ActionChains(driver).send_keys(title).perform()
            logger.debug("Title set via selector: %s", sel)
            return True
        except (NoSuchElementException, WebDriverException):
            continue

    logger.warning("Could not locate title input field.")
    return False


def _focus_body(driver: webdriver.Chrome, wait: WebDriverWait) -> bool:
    """Click into the SE3 body area to ensure cursor is positioned there.

    Used before inserting logos or typing company sections.
    Returns True if body area was successfully clicked.
    """
    try:
        area = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "div.se-body, div.__se-body"))
        )
        area.click()
        time.sleep(0.3)
        return True
    except (TimeoutException, NoSuchElementException, WebDriverException):
        return False


def _type_text(driver: webdriver.Chrome, text: str) -> None:
    """Type text at the current SE3 cursor position via ActionChains."""
    ActionChains(driver).send_keys(text).perform()


def _set_content_with_sections(
    driver: webdriver.Chrome,
    wait: WebDriverWait,
    sections: list[dict],
) -> bool:
    """Inject blog content section by section, inserting logos for company sections.

    For each company section:
      1. Try to insert the company logo (best-effort — never fatal).
      2. Press Enter to move past the image.
      3. Type the company text.

    Falls back to plain text injection if body focus fails.
    """
    logo_paths: list[str] = []

    try:
        if not _focus_body(driver, wait):
            logger.warning("Body focus failed — falling back to plain text injection.")
            body = "\n\n".join(s["content"] for s in sections)
            return _set_content(driver, wait, body)

        # Select-all to clear any existing draft content
        ActionChains(driver).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).perform()
        time.sleep(0.1)
        ActionChains(driver).send_keys(Keys.DELETE).perform()
        time.sleep(0.1)

        for sec in sections:
            if sec["type"] == _SEC_TEXT:
                _type_text(driver, sec["content"])
                ActionChains(driver).send_keys(Keys.RETURN).perform()

            elif sec["type"] == _SEC_COMPANY:
                company_name = sec.get("name", "")
                # domain is extracted by discovery AI; empty string = no logo
                logo_domain = sec.get("domain", "")

                # Download logo and attempt SE3 upload (best-effort)
                logo_path = _download_logo(logo_domain)
                if logo_path:
                    logo_paths.append(logo_path)
                    if _insert_logo_se3(driver, logo_path):
                        # Move cursor past the image before typing text
                        ActionChains(driver).send_keys(Keys.RETURN).perform()
                        time.sleep(0.2)
                    else:
                        logger.debug("Logo insert skipped for %s.", company_name)

                _type_text(driver, sec["content"])
                ActionChains(driver).send_keys(Keys.RETURN + Keys.RETURN).perform()

        logger.debug("Sections injected: %d total.", len(sections))
        return True

    finally:
        # Clean up all downloaded logo temp files
        for p in logo_paths:
            try:
                os.unlink(p)
            except OSError:
                pass


def _set_content(driver: webdriver.Chrome, wait: WebDriverWait, body: str) -> bool:
    """Fill in the post body. Returns True on success.

    Tries three strategies in order:
    1. SE3 contenteditable div
    2. SE2 iframe + contenteditable
    3. JavaScript injection on any large contenteditable
    """
    # Strategy 1: SE3 — click into body area (skip title component, use second component)
    try:
        # SE3 body: div.se-body contains the main text area
        area = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "div.se-body, div.__se-body"))
        )
        area.click()
        time.sleep(0.3)
        # Select all existing content and replace
        ActionChains(driver).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).perform()
        ActionChains(driver).send_keys(body).perform()
        logger.debug("Content set via SE3 se-body click.")
        return True
    except (TimeoutException, NoSuchElementException, WebDriverException):
        pass

    # Strategy 2: SE2 — look for a nested content iframe
    try:
        inner_frame = driver.find_element(
            By.CSS_SELECTOR, "iframe.se2_inputarea_frame, iframe#se2_iframe"
        )
        driver.switch_to.frame(inner_frame)
        area = driver.find_element(
            By.CSS_SELECTOR, "div#content_editable, div[contenteditable='true'], body"
        )
        area.click()
        area.send_keys(Keys.CONTROL, "a")
        area.send_keys(body)
        driver.switch_to.parent_frame()
        logger.debug("Content set via SE2 inner frame.")
        return True
    except (NoSuchElementException, WebDriverException):
        try:
            driver.switch_to.parent_frame()
        except WebDriverException:
            pass

    # Strategy 3: JavaScript injection on any sufficiently large contenteditable
    try:
        result = driver.execute_script(
            """
            var areas = document.querySelectorAll('[contenteditable="true"]');
            for (var i = 0; i < areas.length; i++) {
                var el = areas[i];
                if (el.offsetWidth > 100 && el.offsetHeight > 100) {
                    el.focus();
                    el.innerText = arguments[0];
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                    return true;
                }
            }
            return false;
            """,
            body,
        )
        if result:
            logger.debug("Content set via JavaScript fallback.")
            return True
    except WebDriverException as e:
        logger.warning("JavaScript content injection failed: %s", e)

    logger.warning("Could not inject post content into any known editor area.")
    return False


def _publish(driver: webdriver.Chrome, wait: WebDriverWait) -> bool:
    """Click the publish button and confirm in the publish-settings layer.

    Naver Blog SE3 requires two clicks:
      Step 1 — click the toolbar '발행' button → publish-settings layer appears
      Step 2 — click '발행' (confirm_btn) inside the layer → post is actually saved

    JS is used for Step 1 to bypass scroll/visibility issues after content entry.
    """
    # ── Step 1: open publish-settings layer ──────────────────────────────────
    opened = False

    # JS strategy — most reliable when page has scrolled after content entry
    try:
        cls_clicked = driver.execute_script(
            """
            var btns = Array.from(document.querySelectorAll('button'));
            var pub = btns.find(function(b) {
                return b.className.indexOf('publish_btn') !== -1;
            });
            if (pub) {
                pub.scrollIntoView({block:'center'});
                pub.click();
                return pub.className;
            }
            return null;
            """
        )
        if cls_clicked:
            logger.debug("Publish layer opened via JS (class=%s).", cls_clicked)
            opened = True
    except WebDriverException as e:
        logger.debug("JS publish-open failed: %s", e)

    if not opened:
        # Selenium EC fallback
        selectors = [
            (By.XPATH, "//button[contains(@class,'publish_btn')]"),
            (By.CSS_SELECTOR, "button[data-click-area='tpb.publish']"),
            (By.XPATH, "//button[contains(text(), '발행')]"),
        ]
        for by, sel in selectors:
            try:
                btn = WebDriverWait(driver, _SHORT).until(
                    EC.element_to_be_clickable((by, sel))
                )
                btn.click()
                logger.debug("Publish layer opened via selector: %s", sel)
                opened = True
                break
            except (TimeoutException, NoSuchElementException, WebDriverException):
                continue

    if not opened:
        logger.warning("Could not open publish-settings layer.")
        return False

    # ── Step 2: click confirm inside the publish-settings layer ──────────────
    # Layer has class 'layer_publish__*' and the confirm button 'confirm_btn__*'
    confirm_selectors = [
        (By.XPATH, "//div[contains(@class,'layer_publish')]//button[contains(@class,'confirm_btn')]"),
        (By.XPATH, "//div[contains(@class,'layer_popup')]//button[contains(@class,'confirm_btn')]"),
        (By.XPATH, "//div[contains(@class,'layer_btn_area')]//button[contains(@class,'confirm_btn')]"),
        (By.CSS_SELECTOR, "div[class*='layer_publish'] button[class*='confirm_btn']"),
        (By.CSS_SELECTOR, "div[class*='layer_popup'] button[class*='confirm_btn']"),
    ]
    for by, sel in confirm_selectors:
        try:
            btn = WebDriverWait(driver, _LONG).until(
                EC.element_to_be_clickable((by, sel))
            )
            btn.click()
            logger.debug("Publish confirmed via selector: %s", sel)
            return True
        except (TimeoutException, NoSuchElementException, WebDriverException):
            continue

    # Last resort: any visible confirm-looking button inside a visible layer
    try:
        result = driver.execute_script(
            """
            var layers = document.querySelectorAll('[class*="layer_publish"],[class*="layer_popup"]');
            for (var l of layers) {
                if (l.offsetParent === null) continue;
                var btns = l.querySelectorAll('button');
                for (var b of btns) {
                    var cls = b.className || '';
                    if (cls.indexOf('confirm_btn') !== -1) {
                        b.click();
                        return cls;
                    }
                }
            }
            return null;
            """
        )
        if result:
            logger.debug("Publish confirmed via JS layer scan (class=%s).", result)
            return True
    except WebDriverException as e:
        logger.debug("JS layer-confirm failed: %s", e)

    logger.warning("Could not confirm publish in settings layer.")
    return False


def _get_published_url(
    driver: webdriver.Chrome,
    wait: WebDriverWait,
    naver_id: str,
) -> str:
    """Wait for navigation to a published post URL and return it."""
    try:
        # postview/logNo appear only after the compose page transitions to the published post
        wait.until(
            lambda d: "postview" in d.current_url or "logNo" in d.current_url
        )
        return driver.current_url
    except TimeoutException:
        pass
    return f"https://blog.naver.com/{naver_id}"


# ── Public entry point ────────────────────────────────────────────────────────


def post_to_naver(summary: dict) -> str | None:
    """Post weekly valuation report to Naver Blog.

    Args:
        summary: The full _weekly_summary.json content.

    Returns:
        Published post URL if successful, None otherwise.
    """
    naver_id, naver_pw = _get_credentials()
    if not naver_id or not naver_pw:
        logger.warning("NAVER_ID or NAVER_PW not set — skipping Naver Blog.")
        return None

    title, sections = build_blog_sections(summary)
    body_preview = "\n".join(s["content"] for s in sections)
    if not body_preview.strip():
        logger.info("No valuation content to post — skipping Naver Blog.")
        return None

    write_url = _WRITE_URL_TMPL.format(blog_id=naver_id)
    driver: webdriver.Chrome | None = None

    try:
        driver = _build_driver(headless=False)
        wait = WebDriverWait(driver, _LONG)

        # Check for cached session first
        driver.get("https://www.naver.com")
        time.sleep(1)

        if not _is_logged_in(driver):
            logger.info("No cached Naver session — performing login.")
            if not _login(driver, wait, naver_id, naver_pw):
                logger.error("Naver login failed — aborting post.")
                return None
        else:
            logger.info("Using cached Naver session.")

        driver.get(write_url)
        logger.info("Navigated to Naver Blog write page.")

        # Dismiss "resume draft?" popup from any previous incomplete run
        _dismiss_draft_dialog(driver)

        if not _wait_for_editor(driver, WebDriverWait(driver, _LONG)):
            logger.error("SmartEditor did not load — aborting post.")
            return None

        time.sleep(2)  # Allow editor to fully initialise

        if not _set_title(driver, WebDriverWait(driver, _SHORT), title):
            logger.warning("Title could not be set; proceeding anyway.")

        ActionChains(driver).send_keys(Keys.TAB).perform()
        time.sleep(0.5)

        if not _set_content_with_sections(driver, WebDriverWait(driver, _SHORT), sections):
            logger.error("Content injection failed — aborting post.")
            return None

        time.sleep(1)

        if not _publish(driver, WebDriverWait(driver, _SHORT)):
            logger.error("Publish button not found — aborting.")
            return None

        # Return to top-level context before checking URL
        try:
            driver.switch_to.default_content()
        except WebDriverException:
            pass

        post_url = _get_published_url(driver, WebDriverWait(driver, _LONG), naver_id)
        logger.info("Naver Blog post published: %s", post_url)
        return post_url

    except WebDriverException as e:
        logger.error("Selenium error during Naver posting: %s", e)
        return None
    except Exception as e:
        logger.error("Unexpected error during Naver posting: %s", e)
        return None
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass  # Ignore quit errors — driver may already be in a crashed state


# ── CLI ───────────────────────────────────────────────────────────────────────


def _safe_print(text: str) -> None:
    """Print with encoding fallback for Windows cp949 consoles."""
    import sys

    try:
        print(text)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(text.encode(enc, errors="replace").decode(enc, errors="replace"))


def _run_image_diagnostics(driver: webdriver.Chrome, wait: WebDriverWait) -> None:
    """Print SE3 image panel DOM structure after clicking the image toolbar button.

    Used to verify which selectors are live in the current SE3 version so that
    _insert_logo_se3 can be tuned without trial-and-error.  Run via:
        python -m scheduler.naver_poster --diagnose-image
    """
    _safe_print("\n[Diagnostic] Clicking SE3 image button...")
    clicked = False
    for sel in [
        "button.se-image-toolbar-button",
        "button[data-log*='img']",
        "button[title*='이미지']",
        "button[class*='image']",
    ]:
        try:
            btn = WebDriverWait(driver, _SHORT).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
            )
            btn.click()
            _safe_print(f"  ✓ Image button found: {sel}")
            clicked = True
            break
        except (TimeoutException, NoSuchElementException, WebDriverException):
            _safe_print(f"  ✗ Not found: {sel}")

    if not clicked:
        _safe_print("[Diagnostic] No image button found — check toolbar selectors.")
        return

    time.sleep(1.5)

    # Visible elements (offsetParent filter)
    visible = driver.execute_script(
        """
        return Array.from(document.querySelectorAll(
            '[class*="image"],[class*="panel"],[class*="upload"],input[type="file"]'
        ))
        .filter(el => el.offsetParent !== null)
        .map(el => ({tag: el.tagName, cls: el.className.substring(0,120), type: el.type||'', id: el.id||''}));
        """
    )
    _safe_print(f"\n[Diagnostic] Visible image-related elements after click ({len(visible)}):")
    _safe_print(json.dumps(visible, ensure_ascii=False, indent=2))

    # Hidden file inputs (the actual upload target in SE3)
    hidden_file_inputs = driver.execute_script(
        "return Array.from(document.querySelectorAll('input[type=\"file\"]'))"
        ".map(el => ({tag: el.tagName, cls: el.className.substring(0,120), id: el.id||'', hidden: el.offsetParent===null}));"
    )
    _safe_print(f"\n[Diagnostic] All input[type='file'] in DOM (including hidden) ({len(hidden_file_inputs)}):")
    _safe_print(json.dumps(hidden_file_inputs, ensure_ascii=False, indent=2))

    if hidden_file_inputs:
        _safe_print("\n  ✓ Hidden file input found — send_keys on hidden input should work (Selenium standard).")
    else:
        _safe_print("\n  ✗ No input[type='file'] anywhere in DOM — SE3 upload flow is non-standard.")


def main() -> None:
    """CLI entry point for standalone testing."""
    parser = argparse.ArgumentParser(description="Post weekly report to Naver Blog")
    parser.add_argument("--test", action="store_true", help="Dry run: print content only")
    parser.add_argument(
        "--diagnose-image",
        action="store_true",
        help="Open SE3 editor, click the image button, and print the DOM panel structure",
    )
    parser.add_argument("--summary-json", type=str, help="Path to _weekly_summary.json")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )

    # Load .env from project root (two levels up from this file)
    try:
        from dotenv import load_dotenv

        env_file = Path(__file__).resolve().parent.parent / ".env"
        if env_file.exists():
            load_dotenv(env_file, override=False)
    except ImportError:
        pass

    # ── --diagnose-image: open SE3 and inspect image panel DOM ──
    if args.diagnose_image:
        naver_id, naver_pw = _get_credentials()
        if not naver_id or not naver_pw:
            _safe_print("[ERROR] NAVER_ID / NAVER_PW not set in .env")
            return
        write_url = _WRITE_URL_TMPL.format(blog_id=naver_id)
        driver = None
        try:
            driver = _build_driver(headless=False)
            wait = WebDriverWait(driver, _LONG)
            driver.get("https://www.naver.com")
            time.sleep(1)
            if not _is_logged_in(driver):
                if not _login(driver, wait, naver_id, naver_pw):
                    _safe_print("[ERROR] Login failed")
                    return
            driver.get(write_url)
            _dismiss_draft_dialog(driver)
            if not _wait_for_editor(driver, WebDriverWait(driver, _LONG)):
                _safe_print("[ERROR] SmartEditor did not load")
                return
            time.sleep(2)
            # Click into body first so toolbar is active
            _focus_body(driver, WebDriverWait(driver, _SHORT))
            time.sleep(0.5)
            _run_image_diagnostics(driver, wait)
            _safe_print("\n[Diagnostic] Done. Browser stays open for 30s for manual inspection.")
            time.sleep(30)
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
        return

    if args.summary_json:
        summary_path = Path(args.summary_json)
    else:
        results_dir = Path(__file__).resolve().parent.parent / "valuation-results"
        summaries = sorted(results_dir.glob("*/_weekly_summary.json"), reverse=True)
        if not summaries:
            logger.error("No _weekly_summary.json found in valuation-results/")
            return
        summary_path = summaries[0]

    logger.info("Using summary: %s", summary_path)
    with open(summary_path, encoding="utf-8") as f:
        summary = json.load(f)

    title, body = build_blog_content(summary)

    if args.test:
        _safe_print(f"=== TITLE ===\n{title}\n")
        _safe_print(f"=== BODY ({len(body)} chars) ===\n{body[:2000]}")
        return

    url = post_to_naver(summary)
    if url:
        _safe_print(f"Published: {url}")
    else:
        _safe_print("Publishing failed or skipped.")


if __name__ == "__main__":
    main()
