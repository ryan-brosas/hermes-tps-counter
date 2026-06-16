"""Tests for thread safety of the tps-counter plugin."""
import sys
import types
import threading
from unittest.mock import patch

import pytest

from __init__ import (
    _get_session,
    _on_post_api_request,
    get_tps_stats,
    _SessionTPS,
    _SESSIONS,
    _STATE_LOCK,
)


@pytest.fixture(autouse=True)
def mock_hermes_cli():
    """Mock hermes_cli for plugin import compatibility."""
    mod = types.ModuleType("hermes_cli")
    mod._ACTIVE_CLI_INSTANCE = None
    with patch.dict(sys.modules, {"hermes_cli": mod}):
        yield


@pytest.fixture(autouse=True)
def clear_sessions():
    """Reset global state between tests."""
    with _STATE_LOCK:
        _SESSIONS.clear()
    yield
    with _STATE_LOCK:
        _SESSIONS.clear()


class TestConcurrentGetSession:
    def test_concurrent_get_session_returns_same_instance(self):
        """All threads calling _get_session with the same id get the same object."""
        barrier = threading.Barrier(10)
        results = [None] * 10

        def worker(idx):
            barrier.wait()
            results[idx] = _get_session("shared-session")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All results should be the exact same object
        assert all(r is results[0] for r in results)


class TestConcurrentRecord:
    def test_concurrent_record_no_lost_data(self):
        """Concurrent record() calls don't lose any data."""
        session = _get_session("recorder-test")
        n_threads = 50
        barrier = threading.Barrier(n_threads)

        def worker():
            barrier.wait()
            session.record(10, 1.0)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert session.call_count == n_threads
        assert session.total_output_tokens == n_threads * 10


class TestConcurrentGetTPSStats:
    def test_concurrent_get_tps_stats_no_crash(self):
        """Concurrent get_tps_stats calls don't crash or deadlock."""
        # Pre-populate a session
        _on_post_api_request(
            session_id="stats-test",
            usage={"output_tokens": 100},
            api_duration=1.0,
        )

        n_threads = 50
        barrier = threading.Barrier(n_threads)
        results = [None] * n_threads

        def worker(idx):
            barrier.wait()
            results[idx] = get_tps_stats("stats-test")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All results should be identical and valid
        for r in results:
            assert r is not None
            assert r["calls"] == 1
            assert r["total_output_tokens"] == 100


class TestHighConcurrency:
    def test_lock_contention_100_threads(self):
        """100 threads mixing record and stats reads don't deadlock or corrupt."""
        n_threads = 100
        barrier = threading.Barrier(n_threads)
        errors = []

        def worker(idx):
            try:
                barrier.wait()
                if idx % 2 == 0:
                    # Writer: record TPS data
                    _on_post_api_request(
                        session_id="stress-test",
                        usage={"output_tokens": 10},
                        api_duration=0.1,
                    )
                else:
                    # Reader: get stats
                    get_tps_stats("stress-test")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Thread errors: {errors}"

        # Verify data integrity — writers should have recorded
        with _STATE_LOCK:
            state = _SESSIONS.get("stress-test")
        if state is not None:
            # At least some writes should have completed
            assert state.call_count > 0
            assert state.total_output_tokens == state.call_count * 10
