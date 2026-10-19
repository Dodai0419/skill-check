---
name: skill-check
description: Lint an Agent Skill (a folder with SKILL.md) against Anthropic's skill-authoring rules and the SkillMD registry rules, with security flags and a 0-100 score. Use before publishing, sharing or installing a skill.
---

# skill-check

Use when the user writes, edits, reviews or is about to install an Agent Skill, or asks why a skill does not trigger or load.

## How to use
1. From the repo root run one of:
   - one skill: `python skill_check.py path/to/skill`
   - every skill under a folder: `python skill_check.py path/to/skills`
   - machine-readable: add `--json`; also flag em dashes: `--ban-em-dash`
2. Fix every ERROR first (the skill may not load), then WARN. NOTE lines are worth a look but are often fine.
3. Rule ids (FM1, DS2, ST4 ...) are explained in `references/audit-checklist.md`; SK0xx ids are the registry rules.
4. Re-run until it prints no errors, then report the registry score.

## Rules
- Security flags (`executes_scripts`, `network_calls`, `reads_secrets`, `untrusted_install`) are pattern matches. Read the flagged lines before calling a skill unsafe; `untrusted_install` (curl | sh, custom registries) always deserves a close look.
- Judgment rules (is the description specific, are steps in the right order) are not checked by the script; review them yourself with the checklist.
- Exit code: 0 clean, 1 at least one error, 2 nothing found to check.
