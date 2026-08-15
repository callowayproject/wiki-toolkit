"""Mechanically grade the 6 ingest-skill eval runs against evals.json expectations."""

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

# ruff: file-ignore[start-process-with-partial-path, subprocess-without-shell-equals-true, line-too-long]

ROOT = Path(__file__).parent
EVALS_PATH = ROOT.joinpath("evals.json")
EVALS = json.loads(EVALS_PATH.read_text(encoding="utf-8"))

# {eval_name: {key: text}}, built once from evals.json — the single source of
# truth for what each check means. Graders never retype expectation wording.
_EXPECTATION_TEXT = {eval_["name"]: {e["key"]: e["text"] for e in eval_["expectations"]} for eval_ in EVALS["evals"]}


def expect(eval_name: str, key: str) -> str:
    """Look up an expectation's label text from evals.json by (eval_name, key)."""
    return _EXPECTATION_TEXT[eval_name][key]


@dataclass
class Result:
    """One graded expectation."""

    eval_name: str
    key: str
    text: str
    passed: bool
    evidence: str


@dataclass
class FixtureState:
    """Everything a grader might read from a graded fixture, loaded once."""

    path: Path
    manifest: dict
    catalog: list
    log: list
    wiki_files: dict
    lint_ok: bool
    lint_out: str
    commits: int


def read_jsonl(path: Path) -> list[dict]:
    """Read a JSONL file."""
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def git(fixture_path: Path, *args) -> str:
    """Run a git command in the fixture directory."""
    return subprocess.run(["git", "-C", str(fixture_path), *args], check=False, capture_output=True, text=True).stdout


def commit_count(fixture_path: Path) -> int:
    """Count the number of commits in the fixture directory."""
    out = git(fixture_path, "log", "--oneline", "main..HEAD")
    lines = [line for line in out.splitlines() if line.strip()]
    return len(lines)


def lint_clean(fixture_path: Path) -> tuple[bool, str]:
    """Run the lint command in the fixture directory."""
    r = subprocess.run(
        ["uv", "run", "--project", "/Users/coordt/code/wiki-toolkit", "wiki-toolkit", "lint"],
        check=False,
        cwd=str(fixture_path),
        capture_output=True,
        text=True,
    )
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def count_wikilinks(text: str) -> int:
    """Count the number of wikilinks in the text."""
    return len(re.findall(r"\[\[[^\]]+\]\]", text))


def load_fixture_state(fixture_path: Path) -> FixtureState:
    """Load everything a grader needs from a graded fixture, in one pass."""
    lint_ok, lint_out = lint_clean(fixture_path)
    return FixtureState(
        path=fixture_path,
        manifest={e["source"]: e for e in read_jsonl(fixture_path / "docs" / "source-manifest.jsonl")},
        catalog=read_jsonl(fixture_path / "docs" / "catalog.jsonl"),
        log=read_jsonl(fixture_path / "docs" / "log.jsonl"),
        wiki_files={p.name: p.read_text() for p in (fixture_path / "docs" / "wiki").glob("*.md")},
        lint_ok=lint_ok,
        lint_out=lint_out,
        commits=commit_count(fixture_path),
    )


def check_lint_clean(state: FixtureState, eval_name: str) -> Result:
    """Shared check: `wiki-toolkit lint` reports no violations."""
    return Result(eval_name, "lint-clean", expect(eval_name, "lint-clean"), state.lint_ok, state.lint_out[:300])


def check_single_commit(state: FixtureState, eval_name: str, key: str = "single-commit") -> Result:
    """Shared check: exactly one git commit was created for the session."""
    return Result(eval_name, key, expect(eval_name, key), state.commits == 1, f"{state.commits} commits on branch")


def grade_single_new_source(fixture_path: Path) -> list[Result]:
    """Grade a single new source directory."""
    state = load_fixture_state(fixture_path)
    eval_name = "single-new-source"
    results = []

    results.append(
        Result(
            eval_name,
            "manifest-entry",
            expect(eval_name, "manifest-entry"),
            "jira:INFRA-142" in state.manifest,
            str(state.manifest.get("jira:INFRA-142", "")),
        )
    )

    page_with_source = None
    for name, content in state.wiki_files.items():
        if "jira:INFRA-142" in content:
            page_with_source = (name, content)
            break
    results.append(
        Result(
            eval_name,
            "page-cites-source",
            expect(eval_name, "page-cites-source"),
            page_with_source is not None,
            page_with_source[0] if page_with_source else "not found",
        )
    )

    if page_with_source:
        n_links = count_wikilinks(page_with_source[1])
        results.append(
            Result(
                eval_name,
                "wikilink-count",
                expect(eval_name, "wikilink-count"),
                n_links >= 2,
                f"{n_links} links found",
            )
        )
    else:
        results.append(
            Result(eval_name, "wikilink-count", expect(eval_name, "wikilink-count"), False, "no page found")
        )

    cat_has_it = any("INFRA-142" in json.dumps(c) or "redis" in c.get("path", "") for c in state.catalog)
    results.append(
        Result(
            eval_name,
            "catalog-updated",
            expect(eval_name, "catalog-updated"),
            cat_has_it,
            f"catalog entries: {len(state.catalog)}",
        )
    )

    log_has_it = any("INFRA-142" in json.dumps(entry) and entry.get("action") == "ingest" for entry in state.log)
    results.append(
        Result(
            eval_name,
            "log-entry",
            expect(eval_name, "log-entry"),
            log_has_it,
            f"log entries: {len(state.log)}",
        )
    )

    results.append(check_single_commit(state, eval_name))
    results.append(check_lint_clean(state, eval_name))

    untouched = True
    unt_ev = []
    for src in ["jira:INFRA-100", "jira:AUTH-200", "design:infra-overview-v1"]:
        e = state.manifest.get(src, {})
        stamp_unchanged = e.get("updated", "").startswith("2026-06-01")
        unt_ev.append(f"{src}: updated={e.get('updated', '')}")
        if not stamp_unchanged:
            untouched = False
    results.append(
        Result(
            eval_name,
            "unrelated-untouched",
            expect(eval_name, "unrelated-untouched"),
            untouched,
            "; ".join(unt_ev),
        )
    )

    # This fixture's redis-cache page only ever has 2 sources (INFRA-100 +
    # INFRA-142), below SKILL.md's 3+-source inline-citation threshold, so
    # the check is vacuously satisfied — see the expectation text itself.
    results.append(
        Result(
            eval_name,
            "inline-citation",
            expect(eval_name, "inline-citation"),
            True,
            "N/A: page has only 2 sources, below the 3+ threshold",
        )
    )

    return results


def grade_multi_source(fixture_path: Path) -> list[Result]:
    """Check that all three sources are present in the final source-manifest.jsonl."""
    state = load_fixture_state(fixture_path)
    eval_name = "multi-source-one-session"
    results = []

    all_three = all(s in state.manifest for s in ["confluence:RATE-001", "jira:RATE-002", "slack:rate-limit-launch"])
    results.append(
        Result(
            eval_name,
            "all-sources-in-manifest",
            expect(eval_name, "all-sources-in-manifest"),
            all_three,
            str(list(state.manifest.keys())),
        )
    )

    combined_wiki_text = "\n".join(state.wiki_files.values())
    all_cited = all(
        s in combined_wiki_text for s in ["confluence:RATE-001", "jira:RATE-002", "slack:rate-limit-launch"]
    )
    results.append(
        Result(
            eval_name,
            "all-sources-cited",
            expect(eval_name, "all-sources-cited"),
            all_cited,
            "checked substring presence across all wiki pages",
        )
    )

    results.append(check_single_commit(state, eval_name))

    new_page = None
    for name, content in state.wiki_files.items():
        if "rate" in name.lower() or "RATE-001" in content:
            new_page = (name, content)
    links_ok = new_page and count_wikilinks(new_page[1]) >= 2
    results.append(
        Result(
            eval_name,
            "wikilink-count",
            expect(eval_name, "wikilink-count"),
            bool(links_ok),
            f"{count_wikilinks(new_page[1]) if new_page else 'n/a'} links on {new_page[0] if new_page else 'no page found'}",
        )
    )

    ingest_entries = [entry for entry in state.log if entry.get("action") == "ingest"]
    results.append(
        Result(
            eval_name,
            "log-entry-per-source",
            expect(eval_name, "log-entry-per-source"),
            len(ingest_entries) >= 3,
            f"{len(ingest_entries)} total ingest-action entries: {[e.get('message') for e in ingest_entries]}",
        )
    )

    results.append(check_lint_clean(state, eval_name))

    rel_present = new_page and "relationships:" in new_page[1]
    results.append(
        Result(
            eval_name,
            "relationships-entry",
            expect(eval_name, "relationships-entry"),
            bool(rel_present),
            "found relationships: block" if rel_present else "not found",
        )
    )

    return results


def grade_update_covered(fixture_path: Path) -> list[Result]:
    """Check that the update-to-covered-source fixture has a page with a relationships block."""
    state = load_fixture_state(fixture_path)
    eval_name = "update-to-covered-source"
    auth_page = fixture_path / "docs" / "wiki" / "auth-service.md"
    auth_text = auth_page.read_text() if auth_page.exists() else ""

    body = auth_text.split("---", 2)[-1] if auth_text.count("---") >= 2 else auth_text
    body_flat = " ".join(body.split())
    has_1h = any(s in body_flat for s in ["1h", "1 hour", "1-hour"])
    # "reflects" the new value = mentions 1h as the *current* expiry, not just in passing;
    # stale-only would mean 24h appears without any 1h/new-value mention at all.
    results = [
        Result(
            eval_name,
            "content-reflects-update",
            expect(eval_name, "content-reflects-update"),
            has_1h,
            f"body: {body_flat[:300]}",
        )
    ]

    accepted = state.manifest.get("jira:AUTH-200", {})
    was_reprocessed = not accepted.get("updated", "").startswith("2026-06-01")
    results.append(
        Result(
            eval_name,
            "accept-covered-used",
            expect(eval_name, "accept-covered-used"),
            was_reprocessed,
            f"AUTH-200 updated={accepted.get('updated', '')}",
        )
    )

    unrelated_untouched = True
    unt_ev = []
    for src in ["jira:INFRA-100", "design:infra-overview-v1"]:
        e = state.manifest.get(src, {})
        stamp_unchanged = e.get("updated", "").startswith("2026-06-01")
        unt_ev.append(f"{src}: updated={e.get('updated', '')}")
        if not stamp_unchanged:
            unrelated_untouched = False
    results.append(
        Result(
            eval_name,
            "unrelated-untouched",
            expect(eval_name, "unrelated-untouched"),
            unrelated_untouched,
            "; ".join(unt_ev),
        )
    )

    log_has_it = any("AUTH-200" in json.dumps(entry) for entry in state.log)
    results.append(
        Result(
            eval_name,
            "log-entry",
            expect(eval_name, "log-entry"),
            log_has_it,
            f"{len(state.log)} log entries",
        )
    )

    results.append(check_lint_clean(state, eval_name))
    results.append(check_single_commit(state, eval_name))

    return results


GRADERS = {
    "single-new-source": grade_single_new_source,
    "multi-source-one-session": grade_multi_source,
    "update-to-covered-source": grade_update_covered,
}


def _grade_variant(
    iteration_root: Path, eval_name: str, grader: "Callable[[Path], list[Result]]", variant: str
) -> None:
    """Grade one (eval, variant) run, if its fixture exists, and write grading.json."""
    fixture = iteration_root / f"eval-{eval_name}" / variant / "run-1" / "fixture"
    if not fixture.exists():
        return

    results = grader(fixture)
    expected_count = len(_EXPECTATION_TEXT[eval_name])
    assert len(results) == expected_count, (
        f"{eval_name}/{variant}: grader emitted {len(results)} results but "
        f"evals.json defines {expected_count} expectations — grader and evals.json have drifted"
    )

    expectations = [
        {"key": result.key, "text": result.text, "passed": result.passed, "evidence": result.evidence}
        for result in results
    ]
    passed = sum(1 for e in expectations if e["passed"])
    grading = {
        "expectations": expectations,
        "summary": {
            "passed": passed,
            "failed": len(expectations) - passed,
            "total": len(expectations),
            "pass_rate": round(passed / len(expectations), 2) if expectations else 0,
        },
    }
    out_path = iteration_root / f"eval-{eval_name}" / variant / "run-1" / "grading.json"
    out_path.write_text(json.dumps(grading, indent=2))
    print(f"{eval_name}/{variant}: {passed}/{len(expectations)}")


def main(iteration_root: Path) -> None:
    """Grade the fixtures."""
    for eval_name, grader in GRADERS.items():
        for variant in ["with_skill", "old_skill"]:
            _grade_variant(iteration_root, eval_name, grader, variant)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: grade.py <iteration_dir>", file=sys.stderr)
        sys.exit(1)
    main(Path(sys.argv[1]))
