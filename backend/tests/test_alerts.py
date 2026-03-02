"""
Tests for app/core/alerts.py — Slack and Sentry notification helpers.
"""

import pytest
from unittest.mock import MagicMock, patch, call


class TestSlackNotify:
    def test_no_op_without_url(self):
        """slack_notify does nothing when SLACK_WEBHOOK_URL is not set."""
        from app.core.alerts import slack_notify

        with patch("app.core.alerts._slack_post") as mock_post:
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.SLACK_WEBHOOK_URL = None
                slack_notify("hello")
            mock_post.assert_not_called()

    def test_posts_when_url_provided(self):
        from app.core.alerts import slack_notify

        with patch("app.core.alerts._slack_post") as mock_post:
            slack_notify("test message", webhook_url="http://hooks.slack.test/xyz")
            mock_post.assert_called_once_with("http://hooks.slack.test/xyz", "test message")

    def test_slack_error_formats_message(self):
        from app.core.alerts import slack_error

        with patch("app.core.alerts._slack_post") as mock_post:
            slack_error("Something broke", "stack trace here", webhook_url="http://slack.test")
            text = mock_post.call_args[0][1]
            assert "Something broke" in text
            assert "stack trace here" in text
            assert ":rotating_light:" in text

    def test_slack_ok_formats_message(self):
        from app.core.alerts import slack_ok

        with patch("app.core.alerts._slack_post") as mock_post:
            slack_ok("All good", "42 items processed", webhook_url="http://slack.test")
            text = mock_post.call_args[0][1]
            assert "All good" in text
            assert ":white_check_mark:" in text

    def test_post_failure_does_not_raise(self):
        """A bad webhook URL must not crash the calling process."""
        from app.core.alerts import slack_notify
        import urllib.error

        with patch("app.core.alerts._slack_post", side_effect=Exception("timeout")):
            # Should not raise
            slack_notify("msg", webhook_url="http://bad.url")


class TestSentryCapture:
    def test_capture_exception_no_op_without_sentry(self):
        """When sentry_sdk is not configured, capture_exception must not raise."""
        from app.core.alerts import capture_exception

        with patch("builtins.__import__", side_effect=ImportError("no sentry")):
            # Should not raise
            try:
                capture_exception(ValueError("test"))
            except Exception as exc:
                pytest.fail(f"capture_exception raised unexpectedly: {exc}")

    def test_capture_message_no_op_without_sentry(self):
        from app.core.alerts import capture_message

        with patch("builtins.__import__", side_effect=ImportError("no sentry")):
            capture_message("hello")  # must not raise
