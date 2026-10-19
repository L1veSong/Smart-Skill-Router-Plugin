# SSR Position Fix Plan

## Problem
SSR recommendations injected via pre_llm_call hook appear at the END of agent responses. Long responses cause truncation, making SSR invisible to users.

## Root Cause
SSR plugin only supports append mode — no prepend option.

## Solution
Add `position` config option:
- `position: append` (default) — current behavior
- `position: prepend` — show recommendations at response start

## Changes Needed
1. `~/.hermes/plugins/ssr/__init__.py` — modify hook to support position
2. `~/.hermes/config.yaml` — add `position: prepend` under ssr config
3. Shorten recommendation format to single line

## Priority
Low — cosmetic, doesn't affect functionality. Fix with next SSR maintenance session.
