"""Call-brief and signal-backtest renderers."""

from __future__ import annotations

import html
from pathlib import Path

from schemas.models import CallBrief, SignalBacktestResult

SMALL_SAMPLE_DISCLAIMER = (
    "Small-sample event study (target N 8-12). Treat this as qualitative signal "
    "evidence, not a statistically significant edge."
)


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"


def _number(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def _ensure_parent(out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)


def render_call_brief_html(
    out_path: Path,
    brief: CallBrief,
    backtest: SignalBacktestResult | None = None,
) -> Path:
    """Render the call brief to a self-contained HTML file."""
    _ensure_parent(out_path)
    rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(topic.topic)}</td>"
        f"<td>{topic.salience:.2f}</td>"
        f"<td>{html.escape(topic.polarity)}</td>"
        f"<td>{html.escape(topic.evidence_quote)}</td>"
        "</tr>"
        for topic in brief.top_topics
    )
    qna = "\n".join(f"<li>{html.escape(item)}</li>" for item in brief.expected_qna)
    flags = "\n".join(f"<li>{html.escape(item)}</li>" for item in brief.dispersion_flags)
    backtest_html = ""
    if backtest is not None:
        backtest_html = (
            "<section><h2>Signal Backtest</h2>"
            f"<p>Hit ratio: {_pct(backtest.directional_hit_ratio)} | "
            f"IC: {_number(backtest.information_coefficient)} | "
            f"N: {backtest.sample_n}</p>"
            f"<p class=\"disclaimer\">{html.escape(SMALL_SAMPLE_DISCLAIMER)}</p>"
            "</section>"
        )

    content = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>Call Brief {html.escape(brief.target_event_label)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2933; }}
    h1, h2 {{ margin-bottom: 8px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0 24px; }}
    th, td {{ border: 1px solid #d9e2ec; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f0f4f8; }}
    .meta, .disclaimer {{ color: #52606d; }}
    .placeholder {{ min-height: 72px; border: 1px dashed #9fb3c8; padding: 12px; }}
  </style>
</head>
<body>
  <h1>콜 브리프: {html.escape(brief.target_event_label)}</h1>
  <p class="meta">기준일: {brief.as_of.isoformat()}</p>
  <section>
    <h2>주요 토픽</h2>
    <table>
      <thead><tr><th>Topic</th><th>Salience</th><th>Polarity</th><th>Evidence</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </section>
  <section><h2>예상 Q&A</h2><ul>{qna}</ul></section>
  <section><h2>컨센서스 플래그</h2><ul>{flags}</ul></section>
  <section>
    <h2>예상 리비전</h2>
    <p>{html.escape(brief.predicted_revision_direction)} | confidence {brief.confidence:.2f}</p>
  </section>
  {backtest_html}
  <section><h2>분석가 해석</h2><div class="placeholder"></div></section>
</body>
</html>
"""
    out_path.write_text(content, encoding="utf-8")
    return out_path


def render_call_brief_md(
    out_path: Path,
    brief: CallBrief,
    backtest: SignalBacktestResult | None = None,
) -> Path:
    """Render the call brief as Markdown."""
    _ensure_parent(out_path)
    lines = [
        f"# 콜 브리프: {brief.target_event_label}",
        "",
        f"- 기준일: {brief.as_of.isoformat()}",
        f"- 예상 리비전: {brief.predicted_revision_direction}",
        f"- confidence: {brief.confidence:.2f}",
        "",
        "## 주요 토픽",
        "",
        "| Topic | Salience | Polarity | Evidence |",
        "|---|---:|---|---|",
    ]
    lines.extend(
        f"| {topic.topic} | {topic.salience:.2f} | {topic.polarity} | {topic.evidence_quote} |"
        for topic in brief.top_topics
    )
    lines.extend(["", "## 예상 Q&A", ""])
    lines.extend(f"- {item}" for item in brief.expected_qna)
    lines.extend(["", "## 컨센서스 플래그", ""])
    lines.extend(f"- {item}" for item in brief.dispersion_flags)
    if backtest is not None:
        lines.extend(
            [
                "",
                "## Signal Backtest",
                "",
                f"- Hit ratio: {_pct(backtest.directional_hit_ratio)}",
                f"- IC: {_number(backtest.information_coefficient)}",
                f"- N: {backtest.sample_n}",
                f"- {SMALL_SAMPLE_DISCLAIMER}",
            ]
        )
    lines.extend(["", "## 분석가 해석", "", ""])
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def render_signal_backtest_md(out_path: Path, result: SignalBacktestResult) -> Path:
    """Render the signal backtest as a Markdown table."""
    _ensure_parent(out_path)
    lines = [
        "# Signal Backtest",
        "",
        "| Event | T0 | Tone | Predicted | CAR T+1d | CAR T+5d | Hit |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for event in result.events:
        hit = "n/a" if event.direction_match_t1 is None else str(event.direction_match_t1)
        lines.append(
            f"| {event.event_label} | {event.t0.isoformat()} | {event.signal_tone} | "
            f"{event.predicted_sign} | {_pct(event.car_t1)} | {_pct(event.car_t5)} | {hit} |"
        )
    lines.extend(
        [
            "",
            f"- Hit ratio: {_pct(result.directional_hit_ratio)}",
            f"- IC: {_number(result.information_coefficient)}",
            f"- Sample N: {result.sample_n}",
            f"- Window: {result.window_primary}",
            f"- {SMALL_SAMPLE_DISCLAIMER}",
        ]
    )
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def render_signal_backtest_html(out_path: Path, result: SignalBacktestResult) -> Path:
    """Render the signal backtest as a self-contained HTML table."""
    _ensure_parent(out_path)
    rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(event.event_label)}</td>"
        f"<td>{event.t0.isoformat()}</td>"
        f"<td>{html.escape(event.signal_tone)}</td>"
        f"<td>{event.predicted_sign}</td>"
        f"<td>{_pct(event.car_t1)}</td>"
        f"<td>{_pct(event.car_t5)}</td>"
        f"<td>{'n/a' if event.direction_match_t1 is None else event.direction_match_t1}</td>"
        "</tr>"
        for event in result.events
    )
    content = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>Signal Backtest</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2933; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0 24px; }}
    th, td {{ border: 1px solid #d9e2ec; padding: 8px; text-align: left; }}
    th {{ background: #f0f4f8; }}
    .disclaimer {{ color: #52606d; }}
  </style>
</head>
<body>
  <h1>Signal Backtest</h1>
  <table>
    <thead><tr><th>Event</th><th>T0</th><th>Tone</th><th>Predicted</th><th>CAR T+1d</th><th>CAR T+5d</th><th>Hit</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <p>Hit ratio: {_pct(result.directional_hit_ratio)} | IC: {_number(result.information_coefficient)} | N: {result.sample_n}</p>
  <p class="disclaimer">{html.escape(SMALL_SAMPLE_DISCLAIMER)}</p>
</body>
</html>
"""
    out_path.write_text(content, encoding="utf-8")
    return out_path
