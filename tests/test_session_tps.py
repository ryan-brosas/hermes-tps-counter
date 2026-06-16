"""Tests for _SessionTPS class."""
import time
from unittest.mock import patch

import pytest

from __init__ import _SessionTPS


class TestSessionTPSRecord:
    def test_record_valid(self):
        s = _SessionTPS()
        s.record(100, 2.0)
        assert s.call_count == 1
        assert s.total_output_tokens == 100
        assert s.total_duration == 2.0
        assert s.last_call_output_tokens == 100
        assert s.last_call_duration == 2.0
        assert s.last_call_tps == 50.0

    def test_record_zero_tokens_noop(self):
        s = _SessionTPS()
        s.record(0, 2.0)
        assert s.call_count == 1  # record always increments
        assert s.total_output_tokens == 0
        # last_call_tps stays 0 because output_tokens=0 => 0/2=0
        assert s.last_call_tps == 0.0

    def test_record_zero_duration_noop_tps(self):
        s = _SessionTPS()
        s.record(100, 0.0)
        assert s.call_count == 1
        assert s.total_output_tokens == 100
        assert s.last_call_tps == 0.0  # duration<=0 branch

    def test_record_multiple_accumulates(self):
        s = _SessionTPS()
        s.record(100, 2.0)
        s.record(200, 4.0)
        assert s.call_count == 2
        assert s.total_output_tokens == 300
        assert s.total_duration == 6.0


class TestAvgTps:
    def test_avg_tps_calculated(self):
        s = _SessionTPS()
        s.record(100, 2.0)
        assert s.avg_tps == 50.0

    def test_avg_tps_multiple_calls(self):
        s = _SessionTPS()
        s.record(100, 2.0)  # 50 tps
        s.record(200, 4.0)  # 50 tps
        assert s.avg_tps == 50.0

    def test_avg_tps_zero_duration(self):
        s = _SessionTPS()
        assert s.avg_tps == 0.0


class TestTurnTps:
    def test_turn_tps_basic(self):
        s = _SessionTPS()
        s.record(100, 1.0)
        with patch("time.time", return_value=s.turn_start_time + 2.0):
            # tokens=100, elapsed=2.0 => 50 tps
            assert s.turn_tps == 50.0

    def test_turn_tps_zero_elapsed(self):
        s = _SessionTPS()
        s.record(100, 1.0)
        # Mock time so elapsed == 0 exactly
        with patch("time.time", return_value=s.turn_start_time):
            assert s.turn_tps == 0.0

    def test_turn_tps_zero_tokens(self):
        s = _SessionTPS()
        # no record() calls, total_output_tokens == turn_start_tokens == 0
        assert s.turn_tps == 0.0

    def test_reset_turn_updates_markers(self):
        s = _SessionTPS()
        s.record(100, 1.0)
        t1 = time.time() + 10.0
        with patch("time.time", return_value=t1):
            s.reset_turn()
        assert s.turn_start_tokens == 100
        assert s.turn_start_time == t1
        # After reset, turn_tps should be 0 (no new tokens)
        assert s.turn_tps == 0.0


class TestSummaryLine:
    def test_summary_line_with_data(self):
        s = _SessionTPS()
        s.record(1500, 2.0)
        line = s.summary_line()
        assert "750.0 tok/s" in line
        assert "peak 750.0" in line
        assert "out 1.5K" in line

    def test_summary_line_multiple_calls(self):
        s = _SessionTPS()
        s.record(100, 2.0)
        s.record(200, 4.0)
        line = s.summary_line()
        assert "avg" in line  # call_count > 1

    def test_summary_line_empty(self):
        s = _SessionTPS()
        assert s.summary_line() == ""

    def test_summary_line_zero_tokens(self):
        s = _SessionTPS()
        s.record(0, 2.0)
        # last_call_tps=0, total_output_tokens=0 => empty
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


class TestPeakTps:
    def test_peak_tps_tracked(self):
        s = _SessionTPS()
        s.record(100, 2.0)  # 50 tps
        assert s.peak_tps == 50.0
        s.record(300, 2.0)  # 150 tps
        assert s.peak_tps == 150.0

    def test_peak_tps_not_lowered(self):
        s = _SessionTPS()
        s.record(300, 2.0)  # 150 tps
        s.record(100, 4.0)  # 25 tps
        assert s.peak_tps == 150.0


class TestCallCount:
    def test_call_count_increments(self):
        s = _SessionTPS()
        assert s.call_count == 0
        s.record(100, 1.0)
        assert s.call_count == 1
        s.record(200, 2.0)
        assert s.call_count == 2
