"""naver_poster._build_driver — zombie-profile recovery retry tests."""

import pytest
from selenium.common.exceptions import SessionNotCreatedException

from scheduler import naver_poster


class _FakeDriver:
    def __init__(self):
        self.scripts = []

    def execute_script(self, script):
        self.scripts.append(script)


def _patch_common(monkeypatch, tmp_path):
    monkeypatch.setattr(naver_poster, "_PROFILE_DIR", tmp_path / "profile")
    monkeypatch.setattr(naver_poster, "_make_service", lambda: None)
    monkeypatch.setattr(naver_poster.time, "sleep", lambda *_: None)


class TestBuildDriverRetry:
    def test_retries_once_after_session_not_created(self, monkeypatch, tmp_path):
        _patch_common(monkeypatch, tmp_path)
        killed_calls = []
        monkeypatch.setattr(
            naver_poster,
            "_kill_zombie_profile_chrome",
            lambda: killed_calls.append(1) or 1,
        )

        attempts = []

        def fake_chrome(options=None, service=None):
            attempts.append(1)
            if len(attempts) == 1:
                raise SessionNotCreatedException(
                    msg="session not created: Chrome instance exited"
                )
            return _FakeDriver()

        monkeypatch.setattr(naver_poster.webdriver, "Chrome", fake_chrome)

        driver = naver_poster._build_driver()

        assert len(attempts) == 2
        assert killed_calls == [1]
        assert isinstance(driver, _FakeDriver)
        # anti-automation script still applied on the retried driver
        assert any("webdriver" in s for s in driver.scripts)

    def test_second_failure_propagates(self, monkeypatch, tmp_path):
        _patch_common(monkeypatch, tmp_path)
        monkeypatch.setattr(naver_poster, "_kill_zombie_profile_chrome", lambda: 0)

        def always_fail(options=None, service=None):
            raise SessionNotCreatedException(msg="Chrome instance exited")

        monkeypatch.setattr(naver_poster.webdriver, "Chrome", always_fail)

        with pytest.raises(SessionNotCreatedException):
            naver_poster._build_driver()

    def test_success_path_does_not_kill(self, monkeypatch, tmp_path):
        _patch_common(monkeypatch, tmp_path)
        monkeypatch.setattr(
            naver_poster,
            "_kill_zombie_profile_chrome",
            lambda: pytest.fail("must not be called on clean launch"),
        )
        monkeypatch.setattr(
            naver_poster.webdriver, "Chrome", lambda options=None, service=None: _FakeDriver()
        )

        driver = naver_poster._build_driver()
        assert isinstance(driver, _FakeDriver)


class TestKillZombieProfileChrome:
    def test_returns_zero_on_non_windows(self, monkeypatch):
        monkeypatch.setattr(naver_poster.sys, "platform", "linux")
        assert naver_poster._kill_zombie_profile_chrome() == 0
