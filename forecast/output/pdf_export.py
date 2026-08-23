"""Chrome headless wrapper — HTML report -> PDF.

Reuses the career/_build_pdf.py pattern. Chrome's print-to-PDF respects
@media print CSS in the HTML template.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def find_chrome() -> str | None:
    """Locate chrome.exe on Windows. Returns None if not installed."""
    for candidate in CHROME_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return shutil.which("chrome") or shutil.which("chrome.exe")


def html_to_pdf(html_path: Path, pdf_path: Path) -> Path:
    """Convert an HTML report to PDF via Chrome headless.

    Args:
        html_path: Source HTML (must be absolute file:// compatible path).
        pdf_path: Target PDF.

    Returns:
        pdf_path on success.

    Raises:
        FileNotFoundError: Chrome not installed.
        subprocess.CalledProcessError: Chrome exited non-zero.
        NotImplementedError: Codex implementation (chrome flags, error handling).
    """
    chrome = find_chrome()
    if chrome is None:
        raise FileNotFoundError("Chrome not found — install Chrome or use a different PDF backend.")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        f"--print-to-pdf={pdf_path}",
        html_path.resolve().as_uri(),
    ]
    subprocess.run(cmd, check=True)
    return pdf_path
