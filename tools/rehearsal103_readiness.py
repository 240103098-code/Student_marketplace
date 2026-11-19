"""Real handler readiness polling with one finite preparation deadline."""
import time

from tools.rehearsal101 import Failure, failure_metadata


def wait_for_receivers(probe, diagnostics, *, deadline, clock=time.monotonic, sleep=time.sleep):
    began = clock()
    for role in ("traces", "logs", "metrics"):
        value = {"ready": False, "attempts": []}
        diagnostics[role] = value
        while clock() < deadline:
            attempt_began = clock()
            attempt = {"elapsed_seconds": attempt_began - began, "timestamp_unix": time.time()}
            try:
                probe(role, min(deadline, clock() + .5))
                if clock() > deadline:
                    raise TimeoutError()
                attempt["ready"] = True
                attempt["duration_seconds"] = clock() - attempt_began
                value["attempts"].append(attempt)
                value.update(ready=True, elapsed_seconds=clock() - began)
                break
            except Exception as error:
                attempt.update(ready=False, **failure_metadata(error))
                attempt["duration_seconds"] = clock() - attempt_began
                value["attempts"].append(attempt)
                sleep(min(.05, max(0, deadline - clock())))
        if not value["ready"]:
            value["elapsed_seconds"] = clock() - began
            raise Failure("receiver-startup-" + role)
