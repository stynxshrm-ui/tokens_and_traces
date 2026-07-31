"""
01_clean.py
Baseline agent loop. Tool calls within a turn run sequentially.
Correct, boring, slow. This is what the team shipped first.

Run: python3 01_clean.py
"""

import time
from mock_claude import MockClaude, execute_tool, FINAL_ANSWER


class Agent:
    def __init__(self):
        self.client = MockClaude()
        self.history = []          # every tool result gets appended here
        self.completed_steps = 0   # one increment per tool call

    def record_result(self, tool_name, result):
        # single-threaded here, so this is safe by construction --
        # there's no other thread that could interleave with it.
        idx = len(self.history)
        self.history.append({"step": idx, "tool": tool_name, "result": result})
        self.completed_steps += 1

    def run_turn(self, tool_calls):
        for name, args, latency in tool_calls:
            result = execute_tool(name, args, latency)
            self.record_result(name, result)

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

    print(f"[clean] answer: {answer}")
    print(f"[clean] wall time: {elapsed:.2f}s")
    print(f"[clean] completed_steps counter: {agent.completed_steps}")
    print(f"[clean] history length: {len(agent.history)}")
    print(f"[clean] history entries present (0..{len(agent.history)-1}):")
    for entry in agent.history:
        print(f"    step {entry['step']}: {entry['tool']} -> {entry['result']}")


if __name__ == "__main__":
    main()
