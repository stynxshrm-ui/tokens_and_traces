# 🎯 LLM Routing: From Dashboard Hero to Business Disaster

**"Optimize what matters. Don't let the dashboard lie to you."**

---

A complete demonstration of why **cost per request** is a vanity metric and **cost per successful request** is the only metric that matters.

---

## 🎥 Watch the Video

[Link to your YouTube video]

---

## 📖 The Story

This repository tells a story in 4 scripts:

1. **`01_clean.py`** — Baseline: Everything goes to Sonnet. Expensive, but it works.
2. **`01_broke,py / 02_broken.py`** — The innocent-looking change: A 10-line router (word count + keywords) that destroys your economics.
3. **`03_instrumented.py`** — Adding OpenTelemetry traces to see exactly what's happening.
4. **`04_fixed.py`** — The actual fix: Routing by budget (CPS), not task type.


## 🚀 Quick Start

```bash
# Clone the repo
git clone https://github.com/yourusername/llm-routing-demo.git
cd llm-routing-demo

# Install dependencies
pip install -r requirements.txt

# Run the scripts
DEMO=1 python 01_clean.py
DEMO=1 python 02_broken.py
DEMO=1 python 03_instrumented.py
DEMO=1 python 04_fixed.py
```

---

## 📊 The Core Insight

| Metric | What It Shows | Danger |
| :--- | :--- | :--- |
| **Cost per Request** | What you pay to send a prompt | Can be **gamed** — cheap failures hide the real cost |
| **Cost per Successful Request (CPS)** | What you pay to get a **correct** answer | **Can't be gamed** — includes the cost of failures |

### The Dashboard Lie

```
Cost per request dropped 66%  ← Dashboard says: "We're saving money!"
Cost per successful request: $1.02 ← Reality: "We're actually losing money!"
```

---

## 🏗️ The Architecture

### Categories
The simulation includes 8 ticket categories with varying:
- Daily volume (90-1,400 tickets/day)
- Success rates (Haiku: 44-99%, Sonnet: 93-99%)
- Token counts (180-680 input, 90-520 output)
- Complexity (simple vs complex)

### Two Caches
| Cache | Type | Risk |
| :--- | :--- | :--- |
| **Prompt Cache** | System prompt reuse | ✅ Safe — doesn't affect accuracy |
| **Semantic Cache** | Exact duplicate reuse | ⚠️ Risky — can propagate wrong answers |

---

## 📈 The Results

```
                              success  cost/req  cost/success
baseline (all Sonnet, cached)   97.9%   $0.0022       $0.1409
broken (naive router, cached)   88.4%   $0.0013         $1.02
fixed (budget router, cached)   97.9%   $0.0018       $0.1404
```

**Fixed router:** Same accuracy as all-Sonnet, but **automatically routes simple tasks to Haiku** for cost savings.

---

## 🔧 The Production Pattern

The fixed router includes:

1. **Continuous Monitoring** — CPS recomputed from live OTel spans
2. **Fail-Closed Behavior** — Auto-reverts to Sonnet when a route goes bad
3. **Alerting** — Notifies humans when drift is detected
4. **Model Drift Detection** — Handles prompt regressions, model updates, new ticket shapes

### Drift Simulation

```
Simulated drift on password_reset (Haiku success 99% -> 80%):
  haiku_cps=$0.5011  sonnet_cps=$0.0220  -> routes to sonnet
  ALERT: cost_per_successful_request.haiku exceeded 
         cost_per_successful_request.sonnet for password_reset. Reverted.
```

---

## 🧠 Key Takeaways

1. **Cost per request is a vanity metric.** It looks good on a dashboard but doesn't predict business value.
2. **Cost per successful request is the real metric.** It tells you what you actually pay for a correct answer.
3. **Caching is free money.** Always use it. But don't confuse caching for fixing.
4. **Route by budget, not task type.** Don't ask "what's the cheapest way to process this?" Ask "what's the cheapest way to get this RIGHT?"
5. **Continuous monitoring with fail-closed behavior.** Models drift. Your routing should adapt.

---

## 📁 Project Structure

```
common.py             — ticket categories, pricing, cost model, simulation
otel_setup.py          — real OTel SDK tracer + GenAI-semconv span emission
01_clean.py             — baseline (all Sonnet)
02_broken.py            — the bug (naive length/keyword router)
03_instrumented.py      — measured (OTel spans + caching lever isolated)
04_fixed.py             — the fix (budget-aware router + fail-closed drift check)
sweep_for_demo.py       — generates demo_data.json for the HTML visualization
demo_data.json          — sweep output, embedded in demo.html
demo.html               — the payoff visualization
demo_preview_t18.png    — static reference render of the crossover (filming aid)
```

---

## 📝 License

MIT

---

## 🙏 Acknowledgments

Inspired by real-world production issues with LLM routing at scale.


