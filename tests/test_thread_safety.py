"""Thread safety tests for tps-counter plugin."""
import threading

import pytest

from __init__ import _get_session, _SessionTPS, get_tps_stats, _on_post_api_request, _SESSIONS, _STATE_LOCK


@pytest.fixture(autouse=True)
def clear_sessions(monkeypatch):
    monkeypatch.delenv("HERMES_TPS_MAX_SESSIONS", raising=False)
    monkeypatch.delenv("HERMES_TPS_SESSION_TTL_SECONDS", raising=False)
    with _STATE_LOCK:
        _SESSIONS.clear()
    yield
    with _STATE_LOCK:
        _SESSIONS.clear()


class TestConcurrentGetSession:
    def test_concurrent_get_session_same_instance(self):
        barrier = threading.Barrier(20)
        results = []

        def worker():
            barrier.wait()
            results.append(_get_session("shared"))

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(r is results[0] for r in results)

    def test_concurrent_get_session_different_ids(self):
        results = {}

        def worker(sid):
            results[sid] = _get_session(sid)

        threads = [threading.Thread(target=worker, args=(f"s{i}",)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 20
        # All should be distinct instances
        instances = list(results.values())
        for i in range(len(instances)):
            for j in range(i + 1, len(instances)):
                assert instances[i] is not instances[j]


class TestConcurrentRecord:
    def test_concurrent_record_no_lost_data(self):
        session = _get_session("s1")
        n_threads = 50
        records_per_thread = 10
        barrier = threading.Barrier(n_threads)

        def worker():
            barrier.wait()
            for _ in range(records_per_thread):
                session.record(10, 0.1)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert session.call_count == n_threads * records_per_thread
        assert session.total_output_tokens == n_threads * records_per_thread * 10


class TestConcurrentStats:
    def test_concurrent_get_tps_stats_no_crash(self):
        # Pre-populate some sessions
        for i in range(10):
            s = _get_session(f"s{i}")
            s.record(100, 1.0)

        barrier = threading.Barrier(50)
        errors = []

        def reader():
            barrier.wait()
            try:
                for i in range(10):
                    get_tps_stats(f"s{i}")
            except Exception as e:
                errors.append(e)

        def writer():
            barrier.wait()
            try:
                for i in range(10):
                    s = _get_session(f"s{i}")
                    s.record(50, 0.5)
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(25):
            threads.append(threading.Thread(target=reader))
            threads.append(threading.Thread(target=writer))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []

    def test_high_concurrency_100_threads(self):
        barrier = threading.Barrier(100)
        errors = []

        def worker(tid):
            barrier.wait()
            try:
                sid = f"s{tid % 5}"
                state = _get_session(sid)
                state.record(100, 0.5)
                get_tps_stats(sid)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        # Verify sessions were created
        assert len(_SESSIONS) <= 5

    def test_concurrent_pruning_readers_and_writers_no_crash(self, monkeypatch):
        monkeypatch.setenv("HERMES_TPS_MAX_SESSIONS", "3")
        barrier = threading.Barrier(40)
        errors = []
        observed_shapes = []

        def reader(tid):
            barrier.wait()
            try:
                for i in range(20):
                    stats = get_tps_stats(f"s{(tid + i) % 10}")
                    observed_shapes.append(tuple(sorted(stats.keys())))
            except Exception as e:
                errors.append(e)

        def writer(tid):
            barrier.wait()
            try:
                for i in range(20):
                    _on_post_api_request(
                        session_id=f"s{(tid + i) % 10}",
                        usage={"output_tokens": 100},
                        api_duration=0.5,
                    )
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(20):
            threads.append(threading.Thread(target=reader, args=(i,)))
            threads.append(threading.Thread(target=writer, args=(i,)))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(_SESSIONS) <= 3
        assert observed_shapes
        for shape in observed_shapes:
            assert {"calls", "avg_tps", "last_tps", "peak_tps", "total_output_tokens"}.issubset(shape)
