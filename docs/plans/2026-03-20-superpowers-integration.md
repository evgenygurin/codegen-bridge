# Superpowers Integration — Design Document

> **For Claude:** This is a design document, not an implementation plan. It describes what was built and why.

**Goal:** Adapt structural patterns from the [superpowers](https://github.com/obra/superpowers) plugin to codegen-bridge, adding Codegen-specific process skills while avoiding duplication with superpowers (which may be installed alongside).

**Architecture:** Hybrid approach — take structural patterns (SessionStart injection, meta-skill, prompt templates, verification gates) and add 3 new Codegen-specific skills + enhance 3 existing ones.

**Compatibility:** Works both with and without superpowers installed.

---

## What Was Added

### New Skills (3)

1. **`using-codegen-bridge`** — Meta-skill injected at session start. Maps all skills, provides decision tree, detects superpowers presence.
2. **`debugging-failed-runs`** — Systematic 4-phase debugging for failed/stuck agent runs (analogous to superpowers `systematic-debugging`).
3. **`prompt-crafting`** — Guide for writing effective prompts for Codegen agents, with templates and anti-patterns.
4. **`reviewing-agent-output`** — Two-stage review process for agent-created PRs (spec compliance → code quality).

### Enhanced Skills (3)

5. **`executing-via-codegen`** — Added two-stage review gates (spec then quality) after each task completion.
6. **`agent-monitoring`** — Added verification gates: no completion claims without evidence.
7. **`codegen-delegation`** — Added prompt template references and structured template system.

### Infrastructure

8. **SessionStart hook** — Injects `using-codegen-bridge` meta-skill at session start, detects superpowers.
9. **Cross-platform hook wrapper** — `run-hook.cmd` polyglot script (Windows/Unix).
10. **Prompt templates** — Structured templates in `skills/codegen-delegation/templates/`.

---

## Design Decisions

### Why not duplicate superpowers process skills?

Superpowers provides TDD, brainstorming, planning, git worktrees, and code review skills. If both plugins are installed, duplicate skills would conflict. Our skills focus on the **cloud execution domain** that superpowers doesn't cover.

### Why SessionStart hook?

Superpowers uses SessionStart to inject its meta-skill (`using-superpowers`). We do the same for Codegen context — when should tasks be delegated vs done locally? The hook detects superpowers and adjusts messaging.

### Why two-stage review?

Superpowers' `subagent-driven-development` uses spec compliance review + code quality review after each task. We adapt this for cloud agents: after an agent run completes, verify (1) the output matches the task spec, and (2) the code quality is acceptable before moving to the next task.
