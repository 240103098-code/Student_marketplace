"""Bounded observation after all application producers have actually stopped."""
import json
import math
import time

from tools.rehearsal101 import Failure, require

COMPONENTS = ("otlp_http/traces", "otlp_http/logs", "otlp_http/metrics", "prometheusremotewrite")
SIGNALS = ("traces", "logs", "metrics")
RECEIVER_FIELDS = {"accepted", "refused_requests", "refused_records", "unknown_refused_requests", "evicted_files"}


def wait_for_drain(observe, *, clock=time.monotonic, sleep=time.sleep, maximum=12, polls=None):
    require(type(maximum) in (int, float) and 8 < maximum <= 12, "post-stop-drain-budget-unavailable")
    began = clock()
    deadline = began + maximum
    previous = None
    stable_since = None
    polls = [] if polls is None else polls
    previous_counters = None
    while clock() < deadline:
        value = observe(deadline)
        require(clock() <= deadline, "drain-observation-deadline")
        require(set(value) == {"queues", "collector_counters", "receiver_counters"}, "drain-observation-schema")
        require(set(value["queues"]) == set(COMPONENTS), "drain-queue-missing")
        for queue in value["queues"].values():
            require(set(queue) == {"capacity", "size"} and queue["capacity"] == 2
                and type(queue["size"]) in (int, float) and 0 <= queue["size"] <= 2, "drain-queue-invalid")
        require(bool(value["collector_counters"]) and all(type(v) in (int, float) and math.isfinite(v) and v >= 0
            for v in value["collector_counters"].values()), "drain-collector-counter-missing")
        require(set(value["receiver_counters"]) == set(SIGNALS), "drain-receiver-missing")
        for counter in value["receiver_counters"].values():
            require(set(counter) == RECEIVER_FIELDS and all(type(v) is int and v >= 0 for v in counter.values())
                and counter["accepted"] > 0 and all(v == 0 for k, v in counter.items() if k != "accepted"),
                "drain-complete-receiver-window")
        counters = {**value["collector_counters"], **{signal: counter["accepted"]
            for signal, counter in value["receiver_counters"].items()}}
        if previous_counters is not None:
            require(set(previous_counters) <= set(counters) and all(counters[k] >= previous_counters[k] for k in previous_counters),
                "drain-counter-reset-or-missing")
        previous_counters = counters
        signature = json.dumps(value, sort_keys=True)
        now = clock()
        empty = all(queue["size"] == 0 for queue in value["queues"].values())
        if empty and signature == previous:
            if stable_since is None:
                stable_since = now
        else:
            stable_since = None
        polls.append({"elapsed_seconds": now - began, **value})
        # Pinned0.145: processor batch1s + queue batch0.1s + last retry
        # start<=5s + final per-attempt HTTP1s. Round7.1s up to8s of
        # actual quiescence, including in-flight work absent from queue size.
        if stable_since is not None and now - stable_since >= 8:
            return {"actual_seconds": now - began, "minimum_post_stop_seconds": 8,
                "configured_hidden_work_horizon_seconds": 7.1,
                "stable_counter_window_seconds": now - stable_since, "maximum_seconds": maximum, "polls": polls}
        previous = signature
        sleep(min(.25, max(0, deadline - clock())))
    raise Failure("post-stop-drain-deadline")
