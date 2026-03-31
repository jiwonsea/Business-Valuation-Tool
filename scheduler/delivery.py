"""Weekly valuation delivery content builders (Gamma inputText + Gmail HTML).

MCP tools (Gamma, Gmail) are invoked by the Claude Code agent, not Python.
This module prepares the content strings only.
"""

from __future__ import annotations

from datetime import datetime


def build_company_gamma_text(entry: dict) -> str:
    """Build per-company Gamma presentation input text (Korean).

    Args:
        entry: A single valuation entry from _weekly_summary.json with keys:
            company, market, status, summary_md, market_cap_usd

    Returns:
        Structured Korean text suitable for Gamma generate inputText.
    """
    company = entry.get("company", "Unknown")
    market = entry.get("market", "")
    summary_md = entry.get("summary_md", "")
    market_cap = entry.get("market_cap_usd")

    cap_text = ""
    if market_cap:
        if market_cap >= 1_000_000_000:
            cap_text = f"시가총액: ${market_cap / 1_000_000_000:.1f}B"
        else:
            cap_text = f"시가총액: ${market_cap / 1_000_000:,.0f}M"

    return f"""\
# {company} 기업가치평가 분석 보고서

시장: {market} | {cap_text}
분석일: {datetime.now().strftime('%Y-%m-%d')}

---

{summary_md}

---

## 투자 의견 요약
- 위 분석 결과를 종합하여 투자 매력도를 평가하세요
- 핵심 리스크와 기회 요인을 정리하세요
- 적정 주가 범위를 제시하세요
"""


def build_weekly_summary_gamma_text(summary: dict) -> str:
    """Build weekly summary Gamma presentation input text (Korean).

    Args:
        summary: The full _weekly_summary.json content.

    Returns:
        Structured Korean text for the weekly overview presentation.
    """
    label = summary.get("label", "")
    markets = summary.get("markets", [])
    status = summary.get("status_summary", {})
    valuations = summary.get("valuations", [])

    # Build per-company table rows
    company_lines = []
    for v in valuations:
        if v.get("status") != "success":
            continue
        name = v.get("company", "")
        market = v.get("market", "")
        cap = v.get("market_cap_usd")
        cap_str = f"${cap / 1_000_000_000:.1f}B" if cap and cap >= 1_000_000_000 else (
            f"${cap / 1_000_000:,.0f}M" if cap else "N/A"
        )
        company_lines.append(f"| {name} | {market} | {cap_str} |")

    company_table = "\n".join(company_lines) if company_lines else "| (분석 대상 없음) | - | - |"

    # Discovery highlights
    discoveries = summary.get("discoveries", [])
    discovery_text = ""
    for d in discoveries:
        mkt = d.get("market", "")
        news_count = d.get("news_count", 0)
        cos = d.get("companies", [])
        co_names = ", ".join(c.get("name", "") for c in cos[:5])
        discovery_text += f"- {mkt}: 뉴스 {news_count}건, 발굴 기업: {co_names}\n"

    return f"""\
# 주간 밸류에이션 리포트 — {label}

## 개요
- 대상 시장: {', '.join(markets)}
- 분석 기업: {status.get('success', 0)}개 성공 / {status.get('total', 0)}개 대상
- 실패: {status.get('failed', 0)}개

## 발굴 요약
{discovery_text}

## 분석 기업 한눈에 보기

| 기업명 | 시장 | 시가총액 |
|--------|------|----------|
{company_table}

## 기업별 밸류에이션 요약

{''.join(_company_brief(v) for v in valuations if v.get("status") == "success")}

## 주간 투자 시사점
- 위 분석 결과를 종합하여 이번 주 시장 테마를 정리하세요
- Top picks와 주의 종목을 제시하세요
"""


def _company_brief(entry: dict) -> str:
    """Extract a brief summary section for one company."""
    name = entry.get("company", "")
    md = entry.get("summary_md", "")

    # Extract just the headline metrics from summary_md (first 10 lines)
    lines = md.strip().split("\n")[:10]
    brief = "\n".join(lines)

    return f"""\
### {name}
{brief}

---

"""


def build_gmail_html(summary: dict, gamma_urls: dict) -> str:
    """Build Gmail-compatible HTML email body (Korean).

    Args:
        summary: The full _weekly_summary.json content.
        gamma_urls: Mapping of company names to Gamma URLs.
            Special key "_summary" for the weekly summary presentation.

    Returns:
        HTML string with inline CSS (Gmail-safe, table-based layout).
    """
    label = summary.get("label", "")
    status = summary.get("status_summary", {})
    valuations = summary.get("valuations", [])
    summary_gamma = gamma_urls.get("_summary", "")

    # Build company cards
    company_cards = ""
    for v in valuations:
        if v.get("status") != "success":
            continue

        name = v.get("company", "")
        market = v.get("market", "")
        cap = v.get("market_cap_usd")
        cap_str = f"${cap / 1_000_000_000:.1f}B" if cap and cap >= 1_000_000_000 else (
            f"${cap / 1_000_000:,.0f}M" if cap else "-"
        )
        gamma_url = gamma_urls.get(name, "")
        download_url = v.get("download_url", "")

        links = ""
        if gamma_url:
            links += (
                f'<a href="{gamma_url}" style="color:#1a73e8;text-decoration:none;">'
                f"📊 Gamma</a>"
            )
        if download_url:
            if links:
                links += " &nbsp;|&nbsp; "
            links += (
                f'<a href="{download_url}" style="color:#1a73e8;text-decoration:none;">'
                f"📥 Excel</a>"
            )

        company_cards += f"""\
<tr>
  <td style="padding:12px 16px;border-bottom:1px solid #e0e0e0;">
    <strong>{name}</strong>
    <span style="color:#666;font-size:12px;margin-left:8px;">{market} · {cap_str}</span>
    <br>
    <span style="font-size:13px;margin-top:4px;display:inline-block;">{links}</span>
  </td>
</tr>
"""

    summary_link = ""
    if summary_gamma:
        summary_link = (
            f'<a href="{summary_gamma}" '
            f'style="background:#1a73e8;color:white;padding:10px 20px;'
            f'border-radius:6px;text-decoration:none;font-weight:bold;">'
            f"📋 주간 종합 프레젠테이션 보기</a>"
        )

    return f"""\
<div style="font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;max-width:600px;margin:0 auto;">
  <div style="background:#1a237e;color:white;padding:20px 24px;border-radius:8px 8px 0 0;">
    <h2 style="margin:0;font-size:18px;">📈 주간 밸류에이션 리포트</h2>
    <p style="margin:4px 0 0;font-size:14px;opacity:0.9;">{label}</p>
  </div>

  <div style="background:#f5f5f5;padding:16px 24px;">
    <p style="margin:0;font-size:14px;color:#333;">
      분석 완료: <strong>{status.get('success', 0)}</strong>개 기업
      {f" · 실패: {status.get('failed', 0)}개" if status.get('failed', 0) else ""}
    </p>
    {f'<p style="margin:12px 0 0;text-align:center;">{summary_link}</p>' if summary_gamma else ''}
  </div>

  <table style="width:100%;border-collapse:collapse;background:white;">
    <tr>
      <td style="padding:12px 16px;background:#e8eaf6;font-weight:bold;font-size:14px;">
        기업별 분석 결과
      </td>
    </tr>
    {company_cards}
  </table>

  <div style="padding:16px 24px;background:#fafafa;border-radius:0 0 8px 8px;font-size:12px;color:#999;">
    <p style="margin:0;">
      이 리포트는 자동 생성된 분석 자료입니다. 투자 판단의 참고 자료로만 활용하세요.<br>
      Excel 다운로드 링크는 30일간 유효합니다.
    </p>
  </div>
</div>
"""
