# Companion List Audit: SSR & RTK Removal Case Study

> Date: 2026-06-15 · CMG v5.6.0 pre-release audit

## What happened

SSR (Smart Skill Router) and RTK Rewrite had been in the CMG companion skills list for multiple releases. During the v5.6.0 pre-release audit, both were found to fail the companion criteria (pitfall 5).

## Criteria applied (坑点5)

1. **Auto-perceive** — CMG must be able to detect and interact with the companion without manual configuration
2. **Zero-adapter** — CMG's checklists/scans/intercepts can directly trigger the companion
3. **Complementary** — The companion provides capabilities CMG itself lacks

## SSR (Smart Skill Router) — FAILED

| Criterion | Result | Reason |
|-----------|--------|--------|
| Auto-perceive | ❌ | SSR is an independent `pre_llm_call` plugin. CMG doesn't trigger or discover it. They run in parallel, not in a caller-callee relationship. |
| Zero-adapter | ❌ | CMG doesn't invoke SSR, SSR doesn't invoke CMG. No integration path exists. |
| Complementary | ⚠️ | Weak: SSR matches skills, CMG guards behavior. Different domains entirely. |

**Verdict:** Parallel infrastructure, not a CMG companion. The sentinel micro-scheduler already handles CMG's skill recommendation needs.

## RTK Rewrite — FAILED

| Criterion | Result | Reason |
|-----------|--------|--------|
| Auto-perceive | ❌ | RTK is a Gateway-level plugin. CMG has no awareness of or interaction with terminal output compression. |
| Zero-adapter | ❌ | CMG's token consumption is in LLM context (SKILL.md loading + rule injection), not terminal output. RTK compresses terminal output — a completely different pipeline. |
| Complementary | ❌ | RTK doesn't enhance any CMG function (guard/monitor/produce/scan). It's Hermes infrastructure, not CMG-enhancing. |

**Verdict:** Infrastructure tool, zero relevance to CMG.

## Lesson: periodic retrospective audit

Companion entries that were added early in CMG's development may fail criteria that were clarified later. Schedule a per-release audit:

```bash
# For each companion, verify against three criteria
# If any entry fails ≥2 criteria → remove
```

## Also removed in this audit

- Duplicate `dashboard` entry (listed twice in cross-line shared table)
- Broken table row `agent-s-deployment`
- `cmg-dashboard` (redundant with `dashboard`)
