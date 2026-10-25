"""Pre-submission check against the hackathon rules. Run from the project root:

    python -m scripts.check_submission           # static checks
    python -m scripts.check_submission --tests   # also run the test suite

Exit code is 1 if any automatic check fails. MANUAL items are yours to do.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
rows: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    rows.append((name, "PASS" if ok else "FAIL", detail))


def manual(name: str, detail: str) -> None:
    rows.append((name, "MANUAL", detail))


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def main() -> int:
    license_text = read(ROOT / "LICENSE")
    check("LICENSE is a real MIT license", "MIT License" in license_text and "TODO" not in license_text)

    readme = read(ROOT / "README.md")
    check("README has setup instructions", "Quick start" in readme)
    check("README has judge instructions", "For judges" in readme)
    check("repository URL placeholder replaced (README)", "<your-username>" not in readme,
          "replace <your-username> with your GitHub username")

    required_docs = [
        "docs/problem_statement.md", "docs/architecture.md", "docs/sandbox_limits.md",
        "docs/demo_script.md", "docs/submission_text.md", "docs/submission_checklist.md",
        "docs/official_rules_check.md",
    ]
    for doc in required_docs:
        path = ROOT / doc
        check(f"{doc} exists and has content", path.exists() and path.stat().st_size > 200)

    submission_text = read(ROOT / "docs" / "submission_text.md")
    check("submission text has no unfilled placeholders",
          "<your-username>" not in submission_text and "TODO" not in submission_text)
    check("submission text declares solo entry and no sponsor support",
          "solo" in submission_text.lower() and "none received" in submission_text.lower())

    gitignore = read(ROOT / ".gitignore").splitlines()
    check(".env is excluded from git", ".env" in gitignore)
    check("local database is excluded from git", "*.db" in gitignore)

    empty = [p for p in (ROOT / "app").rglob("*.py") if p.stat().st_size == 0 and p.name != "__init__.py"]
    check("no empty Python modules in app/", not empty,
          ", ".join(str(p.relative_to(ROOT)) for p in empty))

    todo_hits = []
    for folder in ("app", "scripts", "evals"):
        for path in (ROOT / folder).rglob("*.py"):
            if re.search(r"#\s*TODO\b", read(path)):
                todo_hits.append(str(path.relative_to(ROOT)))
    check("no TODO comments in code", not todo_hits, ", ".join(todo_hits))

    offline = ROOT / "evals" / "results" / "offline.json"
    check("offline evaluation results exist", offline.exists(),
          "run: python -m evals.run_eval" if not offline.exists() else "")
    if offline.exists():
        s = json.loads(offline.read_text(encoding="utf-8"))["summary"]
        check("all injected errors caught", s["injected_caught"] == s["injected_total"],
              f"{s['injected_caught']}/{s['injected_total']}")
        check("all clean drafts passed", s["clean_passed"] == s["clean_total"],
              f"{s['clean_passed']}/{s['clean_total']}")

    paraphrase = ROOT / "evals" / "results" / "paraphrase.json"
    check("paraphrase measurement exists", paraphrase.exists(),
          "run: python -m evals.paraphrase_eval" if not paraphrase.exists() else "")

    try:
        json.loads(read(ROOT / "postman" / "evidencegate.postman_collection.json"))
        check("Postman collection is valid JSON", True)
    except json.JSONDecodeError:
        check("Postman collection is valid JSON", False)

    if "--tests" in sys.argv:
        result = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT,
                                capture_output=True, text=True)
        last = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
        check("test suite passes", result.returncode == 0, last)

    manual("GitHub repository is public", "Repository settings.")
    manual("MIT license selected in the About panel", "Repository About panel.")
    manual("Video under 3:00, public on YouTube, link on the form", "Upload and check the length.")
    manual("Video has no unlicensed music or extra trademarks", "Review before uploading.")
    manual("Video shows the desktop application running", "Record the browser screen.")
    manual("Logo rights and resemblance checked", "See docs/official_rules_check.md.")
    manual("Sponsor prize requirements read (if entering for one)", "Not in the rules provided.")
    manual("Financial support declared as none", "On the submission form.")
    manual("Final edits done before the deadline", "No changes after submission.")

    width = max(len(r[0]) for r in rows)
    for name, status, detail in rows:
        suffix = f"  ({detail})" if detail else ""
        print(f"[{status:<6}] {name:<{width}}{suffix}")

    failed = [r for r in rows if r[1] == "FAIL"]
    manual_count = sum(r[1] == "MANUAL" for r in rows)
    print(f"\n{len(rows) - len(failed) - manual_count} automatic checks passed, "
          f"{len(failed)} failed, {manual_count} manual items remain.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
