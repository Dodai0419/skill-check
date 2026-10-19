<div align="center">

# skill-check

**Lint Agent Skills against Anthropic's authoring rules and the SkillMD registry rules in one pass, no deps.**

skill-creator-plus checks a skill the way Anthropic's docs describe; SkillMD scores it the way its registry does. skill-check gives both answers from one Python file.

Works with **Claude Code** and **Codex**.

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg) ![Status: prototype](https://img.shields.io/badge/status-prototype-orange.svg)

</div>

## Quick start
```bash
git clone https://github.com/Dodai0419/skill-check && cd skill-check
python skill_check.py tests/fixtures/with-refs
```
```
WARN   ST6    reference/orphan.md  reference/orphan.md is never linked from SKILL.md, so Claude has no reason to open it. ...
WARN   SC5    scripts/fill.py:2  scripts/fill.py needs the package 'pypdf' but no install line was found anywhere in the skill. ...
Result: 0 errors, 2 warnings, 1 note - no errors.
  registry score 100/100
```
Point it at any folder to check every skill under it: `python skill_check.py ~/.claude/skills`. Add `--json` for machines.

## The problem
- Anthropic's rules (name format, description length, reachable reference files, missing install lines) live in skill-creator-plus, a Python script.
- The registry view (license, stub body, headings, name/folder match, risky `curl | sh` lines, a 0-100 score) lives in SkillMD, a Node CLI with a YAML dependency.
- Checking one skill both ways means two runtimes and two reports, and SkillMD's walker skips a lowercase `skill.md` that Claude Code still loads on Windows.

## The solution
| Idea | Fixes |
|------|-------|
| **Both rule sets, one report** | FM/DS/ST/SC/NM/HK rules plus SK0xx rules, security flags and the registry score |
| **One YAML reader** | SkillMD's checks reuse skill-creator-plus's stdlib frontmatter parser: no `yaml`, no Node |
| **JavaScript-exact port** | UTF-16 lengths and ASCII-only `\b` reproduce SkillMD's numbers to the character |
| **Faster dependency check** | each package's install-line scan runs once per skill instead of once per import |

## Use with Claude Code
```bash
/plugin marketplace add Dodai0419/skill-check
/plugin install skill-check@skill-check
```

## Use with Codex (ChatGPT)
```bash
git clone https://github.com/Dodai0419/skill-check && cp -r skill-check/skills/* ~/.codex/skills/
```
Or copy `AGENTS.md` into your project root.

## Benchmarks
Windows 11, Python 3.11, Node 24, a busy machine (expect large swings; both runs shown). Upstream = `validate_skill.py --json` plus `@skillmds/core` `lint()` run by Node (core only, which is faster than the full `skillmd` CLI); for the tree, `validate_skill.py --all` once per `skills/` folder (24 runs) plus one Node run.

| | original (both tools) | skill-check |
|-|-|-|
| one skill (`tests/fixtures/good-skill`), median of 9 | 963 / 1,617 ms | 423 / 804 ms |
| 461-skill tree (SkillMD repo `plugins/`), median of 3 | 196,970 ms | 119,161 ms |
| lines of code | 1,326 Python + 408 TypeScript | 1,333 (vendored validator) + 205 |
| runtimes / dependencies | Python + Node, `yaml` | Python, 0 |

Before the install-line speed-up in `validate_skill.py`, the tree run was slower than upstream (145,099 vs 132,662 ms): the validator itself is the cost, so the gain there comes from that change, not from the merge.

Same answers: on 461 real skills (the SkillMD repo's own plugin skills plus skill-creator-plus's example) and 88 skills installed on the test machine, the registry part (ok, score, every diagnostic, every security finding with line and snippet) equals `@skillmds/core` `lint()`. On the 463 SkillMD skill folders, the authoring part (counts, passed rules, every finding) equals `validate_skill.py --all`. The 16 fixtures in `tests/` pin both (`python -m unittest -q`).

## Inspired by
- [robonuggets/skill-creator-plus](https://github.com/robonuggets/skill-creator-plus): `validate_skill.py` and `references/audit-checklist.md`, used as-is apart from the speed-up noted in the file.
- [skillmds/skillmd](https://github.com/skillmds/skillmd): the SK0xx rules, security patterns and quality score, ported to Python.

## Roadmap
- [ ] SARIF output for GitHub code scanning.
- [ ] `--fix` for the safe fixes (missing license, quoting a description with `: `).

## License
MIT
