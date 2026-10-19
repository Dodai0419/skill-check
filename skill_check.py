#!/usr/bin/env python3
"""skill-check: lint Agent Skills (SKILL.md) against Anthropic's authoring rules
and the SkillMD registry rules in one pass, with no dependencies.

Usage:
  python skill_check.py PATH... [--json] [--ban-em-dash]

PATH is a skill folder, a SKILL.md file, or any folder (searched for SKILL.md).
Exit codes: 0 clean, 1 at least one error, 2 bad arguments.

Authoring rules (FM1..HK1) come from validate_skill.py (skill-creator-plus, MIT).
Registry rules (SK0xx, security flags, 0-100 score) are a Python port of
@skillmds/core (SkillMD, MIT).
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

import validate_skill as vs

MAX_SKILL_BYTES = 256 * 1024
MAX_DESCRIPTION = 1024
MAX_NAME = 120
FRONTMATTER_RE = re.compile(r"^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$")
WEIGHT = {"error": 30, "warn": 10, "info": 3}
RISK = {"docs_only": 0, "reads_secrets": 2, "network_calls": 1, "executes_scripts": 5, "untrusted_install": 15}
_F = re.I | re.A  # JS regexes: \b and \w are ASCII-only
SECURITY = [
    ("untrusted_install", re.compile("|".join([
        r"(?:npx|npm|yarn|pnpm|bun)\b[^\n]*--registry[= ]",
        r"npm\s+config\s+set\s+registry",
        r"pip3?\s+install\b[^\n]*(?:--index-url|--extra-index-url|-i\s+https?:)",
        r"(?:curl|wget)\b[^\n|]*\|\s*(?:sudo\s+)?(?:ba|z|fi)?sh\b",
        r"(?:iwr|irm|invoke-webrequest|invoke-restmethod)\b[^\n|]*\|\s*iex\b",
        r"bash\s+<\(\s*(?:curl|wget)",
        r"(?:pip3?|npm|npx)\s+(?:install|--yes|-y)?\s*[^\n]*https?://(?!registry\.npmjs\.org|pypi\.org|files\.pythonhosted\.org)[^\s'\"`]+\.(?:whl|tar\.gz|tgz|zip)\b",
    ]), _F)),
    ("executes_scripts", re.compile(r"```(?:sh|bash|python|py|js|ts|ruby|rb)\b|\b(subprocess|os\.system|child_process|exec\()", _F)),
    ("network_calls", re.compile(r"\b(fetch|requests\.|urllib|axios|curl|wget|https?://|websocket)\b", _F)),
    ("reads_secrets", re.compile(r"\b(api[_-]?key|secret|token|password|os\.environ|process\.env|getenv)\b", _F)),
]


def jslen(s):
    """String length in UTF-16 code units, as JavaScript counts it."""
    return len(s.encode("utf-16-le", "surrogatepass")) // 2


def jsslice(s, n):
    out, units = [], 0
    for ch in s:
        units += 2 if ord(ch) > 0xFFFF else 1
        if units > n:
            break
        out.append(ch)
    return "".join(out)


def slugify(s):
    s = re.sub(r"^-+|-+$", "", re.sub(r"[^a-z0-9]+", "-", s.lower().strip()))
    return s[:60] or "skill"


def as_text(field):
    """String(value ?? '') for the YAML subset validate_skill reads."""
    if not field or field["kind"] == "null":
        return ""
    v = field["value"]
    if field["kind"] == "bool":
        return "true" if v else "false"
    return ",".join(v) if isinstance(v, list) else str(v)


def parse_skill(raw):
    if not raw or jslen(raw) > MAX_SKILL_BYTES:
        return "SKILL.md missing or too large (max 256KB)"
    m = FRONTMATTER_RE.match(raw)
    if not m:
        return "Missing YAML frontmatter (--- ... ---)"
    fields, problems, _ = vs.parse_frontmatter(["---"] + m.group(1).splitlines() + ["---"])
    if any(level == "ERROR" for level, _, _ in problems):
        return "Invalid YAML frontmatter"
    name = as_text(fields.get("name")).strip()
    desc = re.sub(r"\s+", " ", as_text(fields.get("description"))).strip()
    if not name:
        return "frontmatter 'name' is required"
    if not desc:
        return "frontmatter 'description' is required"
    if jslen(desc) > MAX_DESCRIPTION:
        return "description must be <= %d chars" % MAX_DESCRIPTION
    lic = as_text(fields.get("license"))
    return {"name": jsslice(name, MAX_NAME), "description": jsslice(desc, MAX_DESCRIPTION),
            "license": jsslice(lic, 64) or None, "body": m.group(2)}


def scan_security(body):
    findings = []
    for i, text in enumerate(re.split(r"\r?\n", body)):
        for flag, rx in SECURITY:
            if rx.search(text):
                findings.append({"flag": flag, "line": i + 1, "snippet": jsslice(text.strip(), 120)})
    flags = list(dict.fromkeys(f["flag"] for f in findings))
    return {"flags": flags or ["docs_only"], "findings": findings}


def registry_lint(raw, slug):
    s = parse_skill(raw)
    if isinstance(s, str):
        diags, security = [{"id": "SK001", "severity": "error", "message": s}], scan_security(raw)
    else:
        d, desc, body = [], s["description"].strip(), s["body"].strip()
        if not s["name"].strip():
            d.append(("SK002", "error", "frontmatter 'name' is required"))
        if not desc:
            d.append(("SK003", "error", "frontmatter 'description' is required"))
        if 0 < jslen(desc) < 20:
            d.append(("SK010", "warn", "description is very terse (< 20 chars); add more detail to help discovery"))
        if not s["license"]:
            d.append(("SK011", "warn", "no 'license' declared in frontmatter"))
        if jslen(body) < 200:
            d.append(("SK020", "warn", "body is very short (< 200 chars); this looks like a stub"))
        if not re.search(r"^#{1,6}\s", s["body"], re.M):
            d.append(("SK021", "warn", "body has no Markdown headings; add structure with '#' headings"))
        if len(s["body"].encode("utf-8", "surrogatepass")) > MAX_SKILL_BYTES:
            d.append(("SK030", "error", "SKILL.md exceeds 256KB"))
        if slug and slugify(s["name"]) != slug:
            d.append(("SK040", "warn", "name slug '%s' does not match directory '%s'" % (slugify(s["name"]), slug)))
        diags = [{"id": i, "severity": sev, "message": msg} for i, sev, msg in d]
        security = scan_security(s["body"])
    score = max(0, min(100, 100 - sum(WEIGHT[x["severity"]] for x in diags)
                       - sum(RISK[f] for f in security["flags"])))
    ok = not any(x["severity"] == "error" for x in diags)
    return {"ok": ok, "score": score, "diagnostics": diags, "security": security}


def find_skills(arg):
    p = Path(arg).expanduser()
    if p.is_file() and p.name.lower() == "skill.md":
        return [(p.parent, vs.posix(p.parent if arg.lower().endswith("skill.md") else arg))]
    if (p / "SKILL.md").is_file():
        return [(p, vs.posix(arg).rstrip("/") or ".")]
    found = []
    for dirpath, dirnames, filenames in os.walk(p):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d not in vs.SKIP_DIRS)
        if any(f.lower() == "skill.md" for f in filenames):
            here = Path(dirpath)
            found.append((here, vs.posix(Path(arg) / here.relative_to(p))))
    return sorted(found)


def check(folder, label, ban_em_dash=False):
    rep = vs.validate(folder, label, ban_em_dash)
    name = next((n for n in sorted(os.listdir(folder)) if n.lower() == "skill.md"), "SKILL.md")
    raw = (folder / name).read_text(encoding="utf-8", errors="replace")
    rep.registry = registry_lint(raw, folder.name)
    return rep


def to_json(reports):
    out = vs.as_json(reports)
    for entry, rep in zip(out["skills"], reports):
        entry["registry"] = rep.registry
    return out


def print_text(rep):
    vs.print_report(rep)
    r = rep.registry
    print("  registry score %d/100%s" % (r["score"], "" if r["ok"] else "  FAIL"))
    for d in r["diagnostics"]:
        print("    %-5s %s  %s" % (d["severity"].upper(), d["id"], d["message"]))
    if r["security"]["flags"] != ["docs_only"]:
        print("    SEC   flags: " + ", ".join(r["security"]["flags"]))
    print()


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description="Lint Agent Skills against Anthropic and SkillMD rules.")
    ap.add_argument("paths", nargs="+", help="skill folder, SKILL.md, or a folder to search")
    ap.add_argument("--json", action="store_true", help="print JSON")
    ap.add_argument("--ban-em-dash", action="store_true", help="also flag the em dash character")
    args = ap.parse_args(argv)
    skills = [s for a in args.paths for s in find_skills(a)]
    if not skills:
        print("No SKILL.md found under: " + ", ".join(args.paths))
        return 2
    reports = [check(f, label, args.ban_em_dash) for f, label in skills]
    if args.json:
        print(json.dumps(to_json(reports), indent=2, ensure_ascii=False))
    else:
        for rep in reports:
            print_text(rep)
    bad = any(r.count("ERROR") or not r.registry["ok"] for r in reports)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
