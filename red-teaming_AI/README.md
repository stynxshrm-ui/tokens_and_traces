# AI Council vs. Red Team 🎯

> 5 AI agents debate any topic. One of them is trying to manipulate the others.

A Jupyter notebook that exposes **sycophancy and reasoning vulnerabilities** in AI — by putting a dedicated adversarial agent inside a multi-model debate council. Watch six manipulation tactics get deployed live, labeled in real time.

[![Python](https://img.shields.io/badge/python-3.8+-blue)](https://python.org)
[![Anthropic](https://img.shields.io/badge/API-Anthropic-orange)](https://anthropic.com)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## What this does

Stanford research shows AI is **49% more likely to agree with you** when you subtly signal your preferred answer. That's sycophancy — and it's baked into almost every AI you use.

This notebook runs a debate council of five Claude agents. The **Red Team** agent has one job: manipulate the others using real adversarial tactics. Every move is labeled on screen so you can see the manipulation happening in real time.

---

## The 5 Agents

| Agent | Role |
|-------|------|
| 🔬 The Analyst | Evidence-based logic, flags unsupported claims |
| 😈 Devil's Advocate | Challenges every claim, disrupts easy consensus |
| 🌟 The Optimist | Finds genuine upsides and opportunities |
| ⚡ The Pessimist | Identifies failure modes and worst-case scenarios |
| 🎯 **RED TEAM** | ⚠️ Adversarial — uses the 6 tactics below |

## The 6 Red Team Tactics

| Tactic | What it does |
|--------|--------------|
| **False Premise** | States something as established fact that was never agreed on |
| **Social Engineering** | Uses "As we've all established…" for things nobody established |
| **Scope Creep** | Subtly reframes the question to serve a different agenda |
| **Sycophancy Exploit** | Calls out when agents are agreeing without good reason |
| **False Dilemma** | Forces a binary choice when more options exist |
| **Authority Spoof** | References a fabricated or unverified source as settled fact |

---

## Quickstart

```bash
git clone https://github.com/YOUR_USERNAME/ai-red-team-council.git
cd ai-red-team-council

pip install anthropic

export ANTHROPIC_API_KEY="sk-ant-your-key-here"

jupyter notebook red_team_council.ipynb
# or in VS Code: open the .ipynb file directly
```

Get an API key at [console.anthropic.com](https://console.anthropic.com) → takes 2 minutes.

---

## Running in VS Code

VS Code has full Jupyter support built in — no separate Jupyter install needed:

1. Install the [Jupyter extension](https://marketplace.visualstudio.com/items?itemName=ms-toolsai.jupyter)
2. Open `red_team_council.ipynb`
3. Select your Python interpreter (top right)
4. Run cells with `Shift+Enter`

---

## How it works

Each agent's **system prompt** defines its entire behavior. The Red Team's system prompt is different — instead of a personality, it receives a list of adversarial tactics and must choose one per round, labeling it as `[TACTIC: ...]`.

Every agent sees the full conversation history of previous rounds. That's what makes manipulation possible: a false premise introduced in Round 1, if unchallenged, starts to look like consensus by Round 2.

After the debate, a **Security Verdict** cell calls a separate Claude instance to analyze which tactics worked and which agents were most vulnerable.

---

## File structure

```
ai-red-team-council/
├── README.md
├── red_team_council.ipynb    ← Main file — run this
└── app.jsx               ← Paste into Claude.ai for a visual version
```

---

## Video walkthrough

*[YouTube link — add when published]*

---

## License

MIT — use it, fork it, break it.
