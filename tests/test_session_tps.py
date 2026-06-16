"""Tests for _SessionTPS class."""
import sys
import time
import types
from unittest.mock import patch

import pytest

from __init__ import _SessionTPS


@pytest.fixture(autouse=True)
def mock_hermes_cli():
    """Mock hermes_cli for plugin import compatibility."""
    mod = types.ModuleType("hermes_cli")
    mod._ACTIVE_CLI_INSTANCE = None
    with patch.dict(sys.modules, {"hermes_cli": mod}):
        yield


class TestRecord:
    def test_record_valid(self):
        s = _SessionTPS()
        s.record(100, 2.0)
        assert s.call_count == 1
        assert s.total_output_tokens == 100
        assert s.total_duration == 2.0
        assert s.last_call_output_tokens == 100
        assert s.last_call_duration == 2.0
        assert s.last_call_tps == 50.0

    def test_record_zero_tokens_is_noop_for_tps(self):
        s = _SessionTPS()
        s.record(0, 2.0)
        assert s.call_count == 1
        assert s.total_output_tokens == 0
        assert s.last_call_tps == 0.0

    def test_record_zero_duration_is_noop_for_tps(self):
        s = _SessionTPS()
        s.record(100, 0.0)
        assert s.call_count == 1
        assert s.total_output_tokens == 100
        assert s.total_duration == 0.0
        assert s.last_call_tps == 0.0

    def test_record_accumulates(self):
        s = _SessionTPS()
        s.record(100, 1.0)
        s.record(200, 2.0)
        assert s.call_count == 2
        assert s.total_output_tokens == 300
        assert s.total_duration == 3.0

    def test_record_updates_peak_tps(self):
        s = _SessionTPS()
        s.record(100, 1.0)  # 100 tok/s
        assert s.peak_tps == 100.0
        s.record(50, 1.0)   # 50 tok/s — lower, peak unchanged
        assert s.peak_tps == 100.0
        s.record(300, 1.0)  # 300 tok/s — new peak
        assert s.peak_tps == 300.0


class TestAvgTPS:
    def test_avg_tps_normal(self):
        s = _SessionTPS()
        s.record(100, 2.0)
        s.record(200, 3.0)
        assert s.avg_tps == 300 / 5  # 60.0

    def test_avg_tps_zero_duration(self):
        s = _SessionTPS()
        assert s.avg_tps == 0.0

    def test_avg_tps_after_zero_duration_record(self):
        s = _SessionTPS()
        s.record(100, 0.0)
        assert s.avg_tps == 0.0


class TestTurnTPS:
    def test_turn_tps_basic(self):
        s = _SessionTPS()
        s.record(100, 1.0)
        s.reset_turn()
        time.sleep(0.05)
        s.record(50, 1.0)
        tps = s.turn_tps
        assert tps > 0

    def test_turn_tps_zero_elapsed(self):
        s = _SessionTPS()
        s.reset_turn()
        assert s.turn_tps == 0.0

    def test_turn_tps_no_new_tokens(self):
        s = _SessionTPS()
        s.record(100, 1.0)
        s.reset_turn()
        assert s.turn_tps == 0.0


class TestResetTurn:
    def test_reset_turn_updates_markers(self):
        s = _SessionTPS()
        s.record(100, 1.0)
        before = s.turn_start_tokens
        s.reset_turn()
        assert s.turn_start_tokens == s.total_output_tokens
        assert s.turn_start_tokens != before


class TestSummaryLine:
    def test_summary_line_with_data(self):
        s = _SessionTPS()
        s.record(100, 1.0)
        line = s.summary_line()
        assert "tok/s" in line
        assert "out" in line

    def test_summary_line_multiple_calls(self):
        s = _SessionTPS()
        s.record(100, 1.0)
        s.record(200, 2.0)
        line = s.summary_line()
        assert "avg" in line
        assert "peak" in line

    def test_summary_line_empty(self):
        s = _SessionTPS()
        assert s.summary_line() == ""


class TestFmtTokens:
    def test_fmt_under_1k(self):
        assert _SessionTPS._fmt_tokens(999) == "999"

    def test_fmt_1k(self):
        assert _SessionTPS._fmt_tokens(1000) == "1.0K"

    def test_fmt_over_1k(self):
        assert _SessionTPS._fmt_tokens(1500) == "1.5K"

    def test_fmt_1m(self):
        assert _SessionTPS._fmt_tokens(1_000_000) == "1.0M"

    def test_fmt_over_1m(self):
        assert _SessionTPS._fmt_tokens(2_500_000) == "2.5M"


class TestCallCount:
    def test_call_count_increments(self):
        s = _SessionTPS()
        assert s.call_count == 0
        s.record(10, 1.0)
        assert s.call_count == 1
        s.record(20, 1.0)
        assert s.call_count == 2
        s.record(30, 1.0)
        assert s.call_count == 3
