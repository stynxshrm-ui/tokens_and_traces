"""
02_broken.py
The "innocent" change from 01_clean.py: tool calls within a turn are
independent (weather, calendar, email don't depend on each other), so
someone wraps run_turn in a ThreadPoolExecutor to cut wall time. Nothing
else changes. record_result is untouched -- it was "just append and
increment" and nobody flagged it as shared mutable state.

Two races live in record_result, both classic, both silent:
  1. completed_steps += 1  -- read-modify-write, not atomic.
  2. idx = len(self.history); ... history.append(...) -- TOCTOU: two
     threads can compute the same idx before either has appended.

Run: python3 02_broken.py
(Re-run a few times -- the exact corruption pattern can shift, the
corruption itself does not.)
"""

import time
from concurrent.futures import ThreadPoolExecutor
from mock_claude import MockClaude, execute_tool, FINAL_ANSWER


class Agent:
    def __init__(self):
        self.client = MockClaude()
        self.history = []
        self.completed_steps = 0

    def record_result(self, tool_name, result):
        idx = len(self.history)
        # small artificial gap so the race window is wide enough to
        # reproduce reliably on every take instead of "most" takes --
        # real-world races are timing-dependent, this just makes the
        # timing dependency land the same way on camera every time.
        time.sleep(0.02)
        self.history.append({"step": idx, "tool": tool_name, "result": result})

        current = self.completed_steps
        time.sleep(0.02)
        self.completed_steps = current + 1

    def run_one(self, call):
        name, args, latency = call
        result = execute_tool(name, args, latency)
        self.record_result(name, result)

    def run_turn(self, tool_calls):
        # THE CHANGE: sequential loop -> thread pool. One line, in
        # review it reads as a pure latency win. Every tool call in
        # this batch is independent -- nobody's output feeds another's
        # input, so it looks safe.
        with ThreadPoolExecutor(max_workers = len(tool_calls)) as pool:
            pool.map(self.run_one, tool_calls)

    def run(self):
        while True:
            tool_calls, is_final = self.client.next_turn()
            if is_final:
                return FINAL_ANSWER
            self.run_turn(tool_calls)


def main():
    agent = Agent()
    start = time.perf_counter()
    answer = agent.run()
    elapsed = time.perf_counter() - start

    print(f"[broken] answer: {answer}")
    print(f"[broken] wall time: {elapsed:.2f}s")
    print(f"[broken] completed_steps counter: {agent.completed_steps}  (expected 5)")
    print(f"[broken] history length: {len(agent.history)}  (expected 5)")
    print(f"[broken] history entries present:")
    seen_idx = {}
    for entry in agent.history:
        seen_idx.setdefault(entry["step"], []).append(entry["tool"])
    for idx in range(max(seen_idx.keys(), default=-1) + 1):
        tools = seen_idx.get(idx, ["<EMPTY>"])
        flag = "  <-- COLLISION" if len(tools) > 1 else ("  <-- MISSING" if tools == ["<EMPTY>"] else "")
        print(f"    step {idx}: {tools}{flag}")


if __name__ == "__main__":
    main()
