"""scheduler package tests — scoring + weekly_run orchestration."""

from datetime import datetime
from unittest.mock import patch, MagicMock

from scheduler.scoring import (
    _stars,
    _count_news_mentions,
    _news_score,
    _size_score,
    _time_decay_weight,
    score_companies,
)


# ── scoring unit tests ──


class TestStars:
    def test_five_stars(self):
        assert _stars(80) == "★★★★★"
        assert _stars(100) == "★★★★★"

    def test_four_stars(self):
        assert _stars(60) == "★★★★☆"
        assert _stars(79) == "★★★★☆"

    def test_three_stars(self):
        assert _stars(40) == "★★★☆☆"
        assert _stars(59) == "★★★☆☆"

    def test_two_stars(self):
        assert _stars(20) == "★★☆☆☆"
        assert _stars(39) == "★★☆☆☆"

    def test_one_star(self):
        assert _stars(0) == "★☆☆☆☆"
        assert _stars(19) == "★☆☆☆☆"


class TestTimeDecay:
    def test_today_weight_is_one(self):
        now = datetime(2026, 3, 31, 12, 0, 0)
        assert _time_decay_weight("2026-03-31T10:00:00", now) >= 0.99

    def test_30_day_old_weight_is_floor(self):
        now = datetime(2026, 3, 31)
        assert _time_decay_weight("2026-03-01T10:00:00", now) == 0.1

    def test_15_day_old_weight_is_mid(self):
        now = datetime(2026, 3, 31)
        w = _time_decay_weight("2026-03-16T10:00:00", now)
        assert 0.4 < w < 0.6

    def test_unparseable_date_returns_neutral(self):
        assert _time_decay_weight("invalid") == 0.5


class TestNewsMentions:
    def test_counts_title_and_description(self):
        now_str = datetime.now().isoformat()
        news = [
            {"title": "삼성전자 실적 발표", "description": "삼성전자가 분기 실적을 공개", "pub_date": now_str},
            {"title": "SK하이닉스 수주", "description": "HBM 관련 뉴스", "pub_date": now_str},
            {"title": "반도체 시장 전망", "description": "삼성전자 포함 주요 기업", "pub_date": now_str},
        ]
        # Today's news -> weight ~1.0 each, 2 mentions -> ~2.0
        samsung = _count_news_mentions("삼성전자", news)
        assert 1.9 <= samsung <= 2.1
        sk = _count_news_mentions("SK하이닉스", news)
        assert 0.9 <= sk <= 1.1
        assert _count_news_mentions("LG전자", news) == 0

    def test_case_insensitive(self):
        now_str = datetime.now().isoformat()
        news = [{"title": "NVIDIA earnings", "description": "Nvidia beats", "pub_date": now_str}]
        result = _count_news_mentions("NVIDIA", news)
        assert 0.9 <= result <= 1.1


class TestNewsScore:
    def test_max_mentions(self):
        assert _news_score(10, 10) == 50

    def test_half_mentions(self):
        assert _news_score(5, 10) == 25

    def test_zero_max(self):
        assert _news_score(0, 0) == 25  # default

    def test_zero_mentions(self):
        assert _news_score(0, 10) == 0


class TestSizeScore:
    def test_large_cap(self):
        assert _size_score(50_000_000_000) == 50  # $50B

    def test_mid_cap(self):
        assert _size_score(5_000_000_000) == 30  # $5B

    def test_small_cap(self):
        assert _size_score(500_000_000) == 10  # $500M

    def test_unknown(self):
        assert _size_score(None) == 20


class TestScoreCompanies:
    @patch("scheduler.scoring._fetch_market_cap_usd")
    def test_scores_and_sorts(self, mock_cap):
        mock_cap.side_effect = [
            50_000_000_000,  # Samsung: large cap
            None,            # NoTicker: unknown
        ]

        companies = [
            {"name": "NoTicker", "ticker": None, "reason": "이슈", "market": "KR"},
            {"name": "삼성전자", "ticker": "005930", "reason": "실적", "market": "KR"},
        ]
        now_str = datetime.now().isoformat()
        news = [
            {"title": "삼성전자 실적", "description": "좋음", "pub_date": now_str},
            {"title": "삼성전자 반도체", "description": "HBM", "pub_date": now_str},
            {"title": "시장 뉴스", "description": "일반", "pub_date": now_str},
        ]

        scored = score_companies(companies, news)

        # Samsung ranked 1st (2 news mentions + large cap)
        assert scored[0]["name"] == "삼성전자"
        assert scored[0]["news_count"] >= 1.9  # time-weighted ~2.0
        assert scored[0]["score"] > scored[1]["score"]
        assert "★" in scored[0]["stars"]

    @patch("scheduler.scoring._fetch_market_cap_usd", return_value=None)
    def test_empty_companies(self, _):
        assert score_companies([], []) == []

    @patch("scheduler.scoring._fetch_market_cap_usd", return_value=None)
    def test_no_news(self, _):
        companies = [{"name": "TestCo", "ticker": "TEST", "reason": "r", "market": "US"}]
        scored = score_companies(companies, [])
        assert len(scored) == 1
        assert scored[0]["news_count"] == 0.0


# ── weekly_run orchestration tests ──


class TestWeeklyRun:
    @patch("scheduler.weekly_run._save_run_start", return_value=None)
    @patch("scheduler.weekly_run._finalize_run")
    @patch("scheduler.weekly_run.score_companies")
    def test_dry_run_skips_valuation(self, mock_score, mock_finalize, mock_save):
        """dry_run=True skips valuation execution."""
        mock_score.return_value = [
            {"name": "TestCo", "stars": "★★★☆☆", "score": 50, "news_count": 3},
        ]

        with patch("discovery.discovery_engine.DiscoveryEngine") as MockEngine:
            instance = MockEngine.return_value
            instance.discover.return_value = {
                "news_count": 10,
                "companies": [{"name": "TestCo", "ticker": "TEST", "reason": "이슈"}],
            }

            from scheduler.weekly_run import run_weekly
            result = run_weekly(markets=["KR"], dry_run=True)

        assert result["valuations"] == []
        assert len(result["discoveries"]) == 1

    @patch("scheduler.weekly_run._save_run_start", return_value=None)
    @patch("scheduler.weekly_run._finalize_run")
    @patch("scheduler.weekly_run.score_companies")
    def test_discovery_error_isolation(self, mock_score, mock_finalize, mock_save):
        """Per-market error isolation: US continues even if KR fails."""
        mock_score.return_value = []

        with patch("discovery.discovery_engine.DiscoveryEngine") as MockEngine:
            instance = MockEngine.return_value
            instance.discover.side_effect = [
                RuntimeError("KR API 실패"),
                {"news_count": 5, "companies": []},
            ]

            from scheduler.weekly_run import run_weekly
            result = run_weekly(markets=["KR", "US"], dry_run=True)

        assert len(result["errors"]) == 1
        assert result["errors"][0]["market"] == "KR"
        assert len(result["discoveries"]) == 1  # only US succeeded
