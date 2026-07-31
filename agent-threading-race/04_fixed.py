"""
04_fixed.py
Same ThreadPoolExecutor, same latency win. The fix is not "go back to
sequential" -- it's putting a lock around the four lines that touch
shared state (index read, append, counter read, counter write) so
they execute as one atomic unit no matter how many threads are racing
to get in. Everything outside that block still runs fully parallel.

Also fails closed: if the invariant (history length == completed_steps
after every write) is ever violated, we raise instead of silently
shipping a corrupted transcript to the model on the next turn.

Run: python3 04_fixed.py
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from mock_claude import MockClaude, execute_tool, FINAL_ANSWER


class Agent:
    def __init__(self):
        self.client = MockClaude()
        self.history = []
        self.completed_steps = 0
        self._lock = threading.Lock()   # THE FIX

    def record_result(self, tool_name, result):
        with self._lock:
            idx = len(self.history)
            self.history.append({"step": idx, "tool": tool_name, "result": result})
            self.completed_steps += 1

            # fail closed: don't let a corrupted transcript reach the
            # model silently. If this ever fires, something upstream
            # of the lock changed and needs to be re-audited.
            if self.completed_steps != len(self.history):
                raise RuntimeError(
                    f"invariant violated: completed_steps={self.completed_steps} "
                    f"!= history_len={len(self.history)}"
                )

    def run_one(self, call):
        name, args, latency = call
        result = execute_tool(name, args, latency)  # still fully concurrent
        self.record_result(name, result)             # only this is serialized

    def run_turn(self, tool_calls):
        with ThreadPoolExecutor(max_workers=len(tool_calls)) as pool:
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

    print(f"[fixed] answer: {answer}")
    print(f"[fixed] wall time: {elapsed:.2f}s")
    print(f"[fixed] completed_steps counter: {agent.completed_steps}  (expected 5)")
    print(f"[fixed] history length: {len(agent.history)}  (expected 5)")
    print(f"[fixed] history entries present (0..{len(agent.history)-1}):")
    for entry in agent.history:
        print(f"    step {entry['step']}: {entry['tool']} -> {entry['result']}")


if __name__ == "__main__":
    main()
