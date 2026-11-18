"""One pending snapshot; soft cadence never replaces actual field deadlines."""
import time

from tools.rehearsal101 import Failure, require


class SnapshotPump:
    def __init__(self, executor, collect, *, clock=time.monotonic, cancel=None, period=3, limit=5):
        self.executor, self.collect, self.clock, self.cancel = executor, collect, clock, cancel
        self.period, self.limit = period, limit
        self.next_due = clock()
        self.future = None
        self.started = self.completed = None

    def _invoke(self, args):
        try:
            return self.collect(*args)
        finally:
            self.completed = self.clock()

    def _result(self):
        self.future.result()  # Surface actual worker exceptions before generic timing.
        require(self.completed is not None and self.completed - self.started <= self.limit,
                "sampler-snapshot-deadline")
        self.future = None

    def tick(self, *args):
        now = self.clock()
        if self.future is not None:
            if self.future.done():
                self._result()
            else:
                require(now - self.started <= self.limit, "sampler-snapshot-deadline")
                return
        if now >= self.next_due:
            self.started, self.completed = now, None
            self.future = self.executor.submit(self._invoke, args)
            self.next_due += self.period

    def close(self, cause=None):
        if cause is not None and self.cancel is not None:
            self.cancel.set()
        # No timeout fiction: all probe I/O is independently bounded, and both
        # snapshot and nested probe executors are joined before owned cleanup.
        self.executor.shutdown(wait=True, cancel_futures=True)
        if self.future is not None:
            try:
                self._result()
            except Failure as error:
                if cause is not None and str(error) == "sampler-cancelled":
                    return
                raise
