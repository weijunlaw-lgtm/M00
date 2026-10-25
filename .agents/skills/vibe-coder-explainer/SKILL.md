---
name: vibe-coder-explainer
description: >-
  Use this skill whenever the user asks to explain code, system architecture,
  algorithms, or workflows to a "vibe coder", asks for a "vibe coder breakdown",
  or wants intuitive, high-level conceptual mental models with visual flowcharts,
  role-based component tables, and zero unnecessary academic jargon.
---

# 🎨 Vibe Coder Explainer Skill

This skill teaches the agent how to translate complex codebases, quantitative algorithms, or backend systems into the **"Vibe Coder"** communication style.

A **"Vibe Coder"** prioritizes high-level mental clarity, visual architecture, punchy metaphors, and practical flow over academic jargon, mathematical clutter, or dry line-by-line syntax commentary.

---

## 🏛️ The 5-Part Vibe Coder Framework

Whenever the user asks to explain something to a "vibe coder", structure the response using this exact 5-part template:

### 1. 🧠 The Big Picture Vibe (The 30,000-ft Mental Model)
- Start with a vivid, intuitive real-world metaphor (e.g. *"Think of parameter space like a topographical mountain landscape..."* or *"Treat this engine like a dual-battery hybrid car..."*).
- Highlight the **core problem** and the **clever fix** in 2–3 punchy sentences.
- Zero dry academic jargon. Use intuitive terms (e.g. *"shock absorbers"* instead of *"volatility-damped dynamic denominators"*).

### 2. 🗺️ The Visual Journey (Mermaid Flowchart)
- Always provide a clean, high-contrast `flowchart TD` or `flowchart LR`.
- Map the journey: **Input Data ➔ Processing Stages ➔ Final Deliverable/Output**.
- Keep node labels short, visual, and engaging.

### 3. 🗂️ The Role-Based Crew Table (The Stack)
Cast each file/module like a member of a movie heist or sports team:

File / Module | The Role | What It Actually Does |
:--- | :--- | :--- |
🎛️ `runner.py` | **The Conductor** | Orchestrates inputs, runs the show, outputs reports.
🧠 `brain.py` | **The Math Brain** | Fast vectorized algorithms, tensor math, smart filters.
⚙️ `engine.py` | **The Muscle** | Executes state machines and runs the actual logic.
📊 `scoreboard.py` | **The Scorekeeper** | Tracks PnL, calculates Sharpe, Max Drawdown, and badges.

### 4. ⚡ The Pipeline in Plain English
- Break down the steps in numbered chunks (e.g. Stage 1, Stage 2).
- Focus on **what is happening to the data**, not the raw for-loops or syntax.
- Emphasize safety guards (e.g. *"Anti-overfitting guard: weeds out one-hit wonders"*).

### 5. 💡 The Takeaway (The Bottom Line)
- The 1-line summary of why this system is awesome.
- The single 1-line command to trigger it.
- Where the user can immediately see the results (links to reports, dashboards, or UI).

---

## 🎯 Tone & Style Rules

1. **Be Punchy & Crisp:** Use active verbs, bold key phrases, and expressive emojis.
2. **Never Dump Raw Code Unprompted:** Show architecture, tables, and workflows first. If code is shown, keep it to a tight, high-impact snippet.
3. **Always Include Clickable Links:** Use GitHub-style markdown links `[file.py](file:///path/to/file.py)` for every file and symbol mentioned.
