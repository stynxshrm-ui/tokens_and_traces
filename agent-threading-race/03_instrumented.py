"""
03_instrumented.py
Same broken loop as 02_broken.py -- nothing about the bug changes.
What's added is OpenTelemetry spans (GenAI semantic conventions,
gen_ai.tool.* attribute names) around each tool execution, plus two
span events marking the exact read and write of the shared state.
Those two events are the whole diagnosis: once you can see the read
and write timestamps for both bugs side by side, the race is obvious.

This intentionally does NOT alert on anything -- it's the trace you'd
pull up after "steps-to-completion" told you something was wrong and
you needed to know why. See the four alerting metrics for what fires
first; this is the drill-down.

Run: python3 03_instrumented.py
Writes: trace.json (consumed by the timeline demo)
"""

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

from mock_claude import MockClaude, execute_tool, FINAL_ANSWER

RUN_START = time.perf_counter()


class JSONCaptureExporter(SpanExporter):
    """Captures finished spans in memory so we can dump one JSON file
    for the demo. In production this is an OTLP exporter pointed at
    whatever backend you use -- capture-to-file is a demo-only stand-in,
    not the pattern to alert on."""

    def __init__(self):
        self.spans = []

    def export(self, spans):
        for s in spans:
            self.spans.append({
                "name": s.name,
                "thread_id": s.attributes.get("thread.id"),
                "thread_name": s.attributes.get("thread.name"),
                "start_rel_s": round((s.start_time / 1e9) - RUN_START_EPOCH, 4),
                "end_rel_s": round((s.end_time / 1e9) - RUN_START_EPOCH, 4),
                "attributes": dict(s.attributes),
                "events": [
                    {
                        "name": e.name,
                        "time_rel_s": round((e.timestamp / 1e9) - RUN_START_EPOCH, 4),
                        "attributes": dict(e.attributes),
                    }
                    for e in s.events
                ],
            })
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass


RUN_START_EPOCH = time.time()
exporter = JSONCaptureExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("tokens-and-traces.agent-loop")


class Agent:
    def __init__(self):
        self.client = MockClaude()
        self.history = []
        self.completed_steps = 0

    def record_result(self, tool_name, result, span):
        idx = len(self.history)
        span.add_event("history_index_read", {"idx_read": idx})
        time.sleep(0.02)
        self.history.append({"step": idx, "tool": tool_name, "result": result})
        span.add_event("history_append", {"idx_written": idx, "history_len_after": len(self.history)})

        current = self.completed_steps
        span.add_event("step_counter_read", {"value_read": current})
        time.sleep(0.02)
        self.completed_steps = current + 1
        span.add_event("step_counter_write", {"value_written": current + 1})

    def run_one(self, call):
        name, args, latency = call
        t = threading.current_thread()
        with tracer.start_as_current_span(
            f"gen_ai.execute_tool",
            attributes={
                "gen_ai.tool.name": name,
                "gen_ai.operation.name": "execute_tool",
                "thread.id": t.ident,
                "thread.name": t.name,
            },
        ) as span:
            result = execute_tool(name, args, latency)
            self.record_result(name, result, span)

    def run_turn(self, tool_calls):
        with ThreadPoolExecutor(max_workers=len(tool_calls)) as pool:
            pool.map(self.run_one, tool_calls)

    def run(self):
        while True:
            tool_calls, is_final = self.client.next_turn()
            if is_final:
                return FINAL_ANSWER
            self.run_turn(tool_calls)


def diagnose(spans):
    """The payoff: sort spans by start time, print overlaps on the
    shared-state critical section directly from event timestamps."""
    print("[instrumented] spans sorted by start time, showing shared-state events:")
    for s in sorted(spans, key=lambda s: s["start_rel_s"]):
        tool = s["attributes"].get("gen_ai.tool.name")
        print(f"    thread={s['thread_name']:<10} tool={tool:<20} "
              f"span=[{s['start_rel_s']:.3f}, {s['end_rel_s']:.3f}]")
        for e in s["events"]:
            print(f"        {e['time_rel_s']:.3f}s  {e['name']:<20} {e['attributes']}")

    # find overlapping (idx_read, idx_written) pairs across threads
    idx_events = []
    for s in spans:
        for e in s["events"]:
            if e["name"] in ("history_index_read", "history_append"):
                idx_events.append((e["time_rel_s"], s["thread_name"], e["name"], e["attributes"]))
    idx_events.sort()
    reads_by_idx = {}
    collisions = []
    for t, thread_name, name, attrs in idx_events:
        if name == "history_index_read":
            idx = attrs["idx_read"]
            reads_by_idx.setdefault(idx, []).append(thread_name)
    for idx, readers in reads_by_idx.items():
        if len(readers) > 1:
            collisions.append((idx, readers))

    print()
    if collisions:
        print("[instrumented] DIAGNOSIS: two threads read the same history index "
              "before either wrote it back:")
        for idx, readers in collisions:
            print(f"    idx={idx} read by threads {readers} -- classic TOCTOU race, "
                  f"not a logic bug in the agent loop.")
    else:
        print("[instrumented] no index collisions observed this run.")


def main():
    agent = Agent()
    start = time.perf_counter()
    answer = agent.run()
    elapsed = time.perf_counter() - start

    print(f"[instrumented] answer: {answer}")
    print(f"[instrumented] wall time: {elapsed:.2f}s")
    print(f"[instrumented] completed_steps counter: {agent.completed_steps}  (expected 5)")
    print(f"[instrumented] history length: {len(agent.history)}  (expected 5)")
    print()

    diagnose(exporter.spans)

    with open("trace.json", "w") as f:
        json.dump(exporter.spans, f, indent=2)
    print()
    print(f"[instrumented] wrote trace.json ({len(exporter.spans)} spans)")


if __name__ == "__main__":
    main()
