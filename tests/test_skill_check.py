"""skill-check must give the same answers as both upstream linters on every fixture."""
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(name):
    with open(os.path.join(ROOT, "tests", name), encoding="utf-8") as f:
        return json.load(f)


def run(*args):
    p = subprocess.run([sys.executable, "skill_check.py", *args], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout


class MatchesUpstream(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code, out = run("tests/fixtures", "--json")
        cls.ours = {s["path"]: s for s in json.loads(out)["skills"]}

    def test_same_skills_found(self):
        want = {s["path"] for s in load("upstream_validator.json")["skills"]}
        self.assertEqual(set(self.ours), want)

    def test_authoring_rules_match_skill_creator_plus(self):
        for s in load("upstream_validator.json")["skills"]:
            mine = {k: v for k, v in self.ours[s["path"]].items() if k != "registry"}
            self.assertEqual(mine, s, s["path"])

    def test_registry_rules_match_skillmd(self):
        for s in load("upstream_skillmd.json"):
            path = s.pop("file")[: -len("/SKILL.md")]
            self.assertEqual(self.ours[path]["registry"], s, path)

    def test_exit_code_is_one_when_any_error(self):
        self.assertEqual(self.code, 1)

    def test_clean_skill_exits_zero_and_prints_score(self):
        code, out = run("tests/fixtures/good-skill")
        self.assertEqual(code, 0, out)
        self.assertIn("registry score 100/100", out)


if __name__ == "__main__":
    unittest.main()
