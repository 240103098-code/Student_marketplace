"""Deterministic scheduler regressions, not substitutes for Linux field samples."""
from concurrent.futures import Future, ThreadPoolExecutor
import threading
import unittest
from unittest.mock import patch

from tools.rehearsal101 import Failure
from tools.rehearsal103_sampling import SnapshotPump


class ManualExecutor:
    def __init__(self):
        self.pending = None
        self.active = self.peak = self.submitted = 0
        self.joined = False
    def submit(self, function, *args):
        if self.pending is not None:
            raise AssertionError("Overlapping snapshot")
        future = Future()
        self.pending = (function, args, future)
        self.active += 1
        self.peak = max(self.active, self.peak)
        self.submitted += 1
        return future
    def complete(self):
        function, args, future = self.pending
        self.pending = None
        try:
            future.set_result(function(*args))
        except BaseException as error:
            future.set_exception(error)
        self.active -= 1
    def shutdown(self, **kwargs):
        if self.pending is not None:
            self.complete()
        self.joined = True


class SnapshotPumpTest(unittest.TestCase):
    def test_real_worker_cooperatively_stops_and_is_joined_before_resource_cleanup(self):
        started, cancellation, finished = threading.Event(), threading.Event(), threading.Event()
        def bounded_probe():
            started.set()
            try:
                if not cancellation.wait(1):
                    raise AssertionError("Probe did not receive cancellation")
            finally:
                finished.set()
        executor = ThreadPoolExecutor(max_workers=1)
        pump = SnapshotPump(executor, bounded_probe, cancel=cancellation)
        pump.tick()
        self.assertTrue(started.wait(1))
        pump.close(Failure("main-phase-failure"))
        self.assertTrue(finished.is_set())
        self.assertTrue(all(not thread.is_alive() for thread in executor._threads))

    def test_controller_cancellation_prevents_new_commands_and_cleanup_reserves_join_time(self):
        from tools.rehearsal103 import Controller
        from tools.rehearsal101 import Rehearsal
        import time
        controller = Controller.__new__(Controller)
        controller.sampler_cancel = threading.Event()
        controller.sampler_cancel.set()
        controller.cleaning = False
        controller.cleanup_outer_deadline = None
        with self.assertRaisesRegex(Failure, "sampler-cancelled"):
            controller.run(["must-never-execute"])
        controller.failed_sampler_join_seconds = 4
        controller.controller_started = time.monotonic() - 10
        controller.record = {"result": "FAIL"}
        with patch.object(Rehearsal, "cleanup", lambda instance: None):
            before = time.monotonic()
            controller.cleanup()
        self.assertTrue(controller.cleaning)
        self.assertLessEqual(controller.cleanup_outer_deadline - before, 86.1)
        self.assertGreaterEqual(controller.record["verified_cleanup_seconds"], 4)

    def test_3_2_second_snapshot_defers_soft_cadence_without_overlap_or_false_failure(self):
        clock, executor = [0], ManualExecutor()
        pump = SnapshotPump(executor, lambda: None, clock=lambda: clock[0])
        pump.tick()
        clock[0] = 3
        pump.tick()
        self.assertEqual(executor.submitted, 1)
        clock[0] = 3.2
        executor.complete()
        pump.tick()
        self.assertEqual(executor.submitted, 2)
        self.assertEqual(executor.peak, 1)
        clock[0] = 6.4
        executor.complete()
        pump.close()
        self.assertTrue(executor.joined)

    def test_over_five_seconds_fails_and_joins_before_cleanup_can_begin(self):
        clock, executor, cancellation = [0], ManualExecutor(), threading.Event()
        pump = SnapshotPump(executor, lambda: None, clock=lambda: clock[0], cancel=cancellation)
        pump.tick()
        clock[0] = 5.01
        with self.assertRaises(Failure) as raised:
            pump.tick()
        with self.assertRaises(Failure):
            pump.close(raised.exception)
        self.assertTrue(cancellation.is_set())
        self.assertTrue(executor.joined)
        self.assertEqual(executor.active, 0)

    def test_actual_inner_failure_is_not_masked_by_three_second_soft_dispatch(self):
        clock, executor = [0], ManualExecutor()
        def fail():
            raise Failure("actual-probe-failure")
        pump = SnapshotPump(executor, fail, clock=lambda: clock[0])
        pump.tick()
        clock[0] = 3
        pump.tick()
        clock[0] = 3.2
        executor.complete()
        with self.assertRaisesRegex(Failure, "actual-probe-failure"):
            pump.tick()
        with self.assertRaisesRegex(Failure, "actual-probe-failure"):
            pump.close()
        self.assertTrue(executor.joined)
        self.assertEqual(executor.peak, 1)
