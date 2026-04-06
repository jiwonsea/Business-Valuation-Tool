"""FinBERT sentiment analysis for financial news headlines.

Lazy-loads the ProsusAI/finbert model on first call. Falls back gracefully
when transformers/torch are not installed (optional dependency).
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Module-level lazy singleton
_pipeline: object | None = None
_load_attempted: bool = False


def _get_pipeline():
    """Lazy-load FinBERT pipeline (cached after first call)."""
    global _pipeline, _load_attempted
    if _load_attempted:
        return _pipeline
    _load_attempted = True

    try:
        from transformers import pipeline as hf_pipeline
        logger.info("[sentiment] FinBERT 모델 로딩 중...")
        _pipeline = hf_pipeline(
            "sentiment-analysis",
            model="ProsusAI/finbert",
            tokenizer="ProsusAI/finbert",
            truncation=True,
            max_length=512,
        )
        logger.info("[sentiment] FinBERT 로딩 완료")
    except ImportError:
        logger.debug("transformers 미설치 — FinBERT 사용 불가")
    except Exception as e:
        logger.warning("[sentiment] FinBERT 로딩 실패: %s", e)

    return _pipeline


def compute_sentiment(
    news: list[dict],
    max_articles: int = 50,
) -> tuple[Optional[float], Optional[str], int]:
    """Run FinBERT on news headlines.

    Args:
        news: List of dicts with 'title' (required) and optional 'description'.
        max_articles: Maximum articles to process.

    Returns:
        (score, label, article_count) where:
          score: -1.0 (bearish) to +1.0 (bullish)
          label: "positive" | "neutral" | "negative"
          article_count: number of articles processed
    """
    pipe = _get_pipeline()
    if pipe is None:
        return None, None, 0

    # Extract text from news items
    texts = []
    for item in news[:max_articles]:
        title = item.get("title", "")
        desc = item.get("description", "")
        text = f"{title}. {desc}".strip() if desc else title.strip()
        if text:
            texts.append(text)

    if not texts:
        return None, None, 0

    # Batch inference
    try:
        results = pipe(texts, batch_size=16)
    except Exception as e:
        logger.warning("[sentiment] FinBERT 추론 실패: %s", e)
        return None, None, 0

    # Aggregate: score = P(positive) - P(negative), averaged
    total_score = 0.0
    for r in results:
        label = r["label"].lower()
        conf = r["score"]
        if label == "positive":
            total_score += conf
        elif label == "negative":
            total_score -= conf
        # neutral contributes 0

    avg_score = total_score / len(results) if results else 0.0
    avg_score = round(max(-1.0, min(1.0, avg_score)), 3)

    if avg_score > 0.1:
        overall_label = "positive"
    elif avg_score < -0.1:
        overall_label = "negative"
    else:
        overall_label = "neutral"

    return avg_score, overall_label, len(texts)
