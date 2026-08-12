"""Build a small, self-contained wiki fixture for ingest-skill evals.

Usage: python build_fixture.py <dest_dir>

Creates <dest_dir> as a git repo with a docs/ tree: schema.md, three
already-ingested wiki pages (Redis Cache, Auth Service, Infrastructure
Overview) cross-linked to each other, plus unprocessed source files under
docs/sources/ for the eval prompts to ingest. Safe to call repeatedly with a
fresh dest_dir per run — each eval needs its own copy since ingest mutates
the tree.
"""

import subprocess
import sys
from pathlib import Path

# ruff: file-ignore[line-too-long, subprocess-without-shell-equals-true, start-process-with-partial-path]

SCHEMA_MD = """# Wiki Schema

## Domain
Widget Co. platform infrastructure — caching, auth, and request-handling middleware.

## Conventions
- File names: lowercase, hyphens, no spaces (e.g., `transformer-architecture.md`)
- Every wiki page starts with YAML frontmatter (see below)
- Use `[[wikilinks]]` to link between pages (minimum 2 outbound links per page)
- When updating a page, always bump the `updated` date
- Every new page must be added to `catalog.jsonl`
- Every action must be appended to `log.jsonl`
- When updating a page with a source that has a `proposed` status, mark the page's status as `proposed`.
- When all sources on a page are `resolved`, mark the page's status as `resolved`.
- Mark any sections referencing a proposed source with "Proposed change" or "Future implementation" to indicate it is not yet done.
- On pages that synthesize 3+ sources, append `^[source_id]` at the end of paragraphs whose claims come from a specific source.
- Mark claims with a confidence marker where relevant: no marker = extracted; `^[inferred]` = LLM-synthesized connection; `^[ambiguous]` = sources disagree.
- The optional `confidence:` frontmatter block rolls up the mix of markers on the page, recomputed and drift-checked by `lint`.
- The optional `relationships:` frontmatter block adds typed, directional edges between pages, on top of plain `[[wikilinks]]`.
- The optional `aliases:` frontmatter field lists alternate names a page is also known by.

## Wiki Document Frontmatter
```yaml
---
title: Page Title
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [from taxonomy below]
sources: [source_id]
source_count: 1
status: resolved
---
```

## Tag Taxonomy
- caching
- infrastructure
- auth
- security
- rate-limiting
- middleware

## Relationship Types

| Type           | Meaning                                                     |
|----------------|--------------------------------------------------------------|
| `extends`      | This page builds on or generalises the target               |
| `implements`   | This page is a concrete realisation of the target concept   |
| `contradicts`  | This page's claims conflict with or refute the target       |
| `derived_from` | This page is based on or adapted from the target            |
| `uses`         | This page depends on or relies on the target                |
| `replaces`     | This page supersedes or deprecates the target                |
| `related_to`   | Catch-all: related but no stronger directional type applies |
"""

WIKI_PAGES = {
    "redis-cache.md": """---
title: Redis Cache
created: 2026-06-01
updated: 2026-06-01
tags: [caching, infrastructure]
sources: [jira:INFRA-100]
source_count: 1
status: resolved
---

Widget Co. uses a single shared Redis instance as the cache layer in front of
the primary datastore. It currently runs with the `noeviction` policy, so
writes fail once `maxmemory` is reached rather than evicting keys.

See [[Infrastructure Overview]] for how the cache fits into the rest of the
stack, and [[Auth Service]] for one of its heaviest callers (session lookups).
""",
    "auth-service.md": """---
title: Auth Service
created: 2026-06-02
updated: 2026-06-02
tags: [auth, security]
sources: [jira:AUTH-200]
source_count: 1
status: resolved
---

The Auth Service issues JWTs on login. Tokens currently expire after 24
hours, with no refresh-token flow — a user has to log in again once the
token lapses.

Session lookups during requests hit [[Redis Cache]]. See
[[Infrastructure Overview]] for the rest of the request path.
""",
    "infrastructure-overview.md": """---
title: Infrastructure Overview
created: 2026-06-03
updated: 2026-06-03
tags: [infrastructure]
sources: [design:infra-overview-v1]
source_count: 1
status: resolved
---

Widget Co.'s platform is a monolith backed by Postgres, with
[[Redis Cache]] in front of it for hot reads and [[Auth Service]] handling
authentication at the edge.
""",
}

PROCESSED_SOURCES = {
    "jira-infra-100.md": ("jira:INFRA-100", "INFRA-100: cache uses noeviction"),
    "jira-auth-200.md": ("jira:AUTH-200", "AUTH-200: JWT expiry is 24h"),
    "design-infra-overview-v1.md": ("design:infra-overview-v1", "Widget Co. infra overview design doc"),
}

NEW_SOURCE_REDIS_EVICTION = """---
source: jira:INFRA-142
processed: false
---

# INFRA-142: Redis OOM crashes under load

**Reporter:** SRE on-call
**Status:** In Progress

The cache node has been OOM-killed three times this week. Root cause: the
Redis instance runs with `maxmemory-policy noeviction`, so once `maxmemory`
is hit, writes error out and the memory keeps climbing from connection/queue
buildup instead of evicting anything.

**Fix:** switch `maxmemory-policy` to `allkeys-lru` so Redis evicts the least
recently used keys once it hits the memory ceiling, instead of erroring and
crashing. Rolled out via the shared Redis config, no application code
change needed.
"""

NEW_SOURCE_RATELIMIT_DESIGN = """---
source: confluence:RATE-001
processed: false
---

# Rate limiting middleware — design

Widget Co.'s API has no rate limiting today; a single misbehaving client can
degrade the service for everyone. Proposal: add a token-bucket rate-limit
middleware in front of every API route, keyed on API key (falling back to
IP for unauthenticated routes). Bucket state is stored in the existing
Redis cache instance — no new infra.

Default limit: 100 requests/minute per key, configurable per route.
"""

NEW_SOURCE_RATELIMIT_TICKET = """---
source: jira:RATE-002
processed: false
---

# RATE-002: Implement rate-limiting middleware

**Status:** In Progress

Implements the token-bucket design from the RATE-001 design doc. Middleware
sits in front of every route, checks/decrements the bucket in Redis, and
returns `429 Too Many Requests` with a `Retry-After` header once a key's
bucket is empty.
"""

NEW_SOURCE_RATELIMIT_SLACK = """---
source: slack:rate-limit-launch
processed: false
---

# #platform-eng, 2026-08-09

**@dana:** rate limiting middleware from RATE-002 is live in prod as of this
morning. default is 100 req/min per API key. if a partner needs a higher
limit, file a ticket, it's configurable per-route.

**@sam:** nice, does this touch the auth service at all?

**@dana:** no, it's a standalone middleware layer, doesn't change how JWTs
are issued or checked. it just sits between the router and the handlers.
"""

# Update to an *already-covered* source (jira:AUTH-200): the same source id
# and file path, overwritten with a field change and `processed` reset.
UPDATED_SOURCE_AUTH_200 = """---
source: jira:AUTH-200
processed: false
---

# AUTH-200: JWT expiry is 24h

**Status:** Done

Token expiry has been changed from 24h to 1h, following the security
review's recommendation to shorten the exposure window for a leaked token.
No refresh-token flow yet — a user simply has to log in again after 1h.
"""


def _write(path: Path, content: str) -> None:
    """
    Writes the given content to the specified file path, creating any necessary parent directories beforehand.

    Args:
        path: The file system path where the content should be written.
        content: The textual content to be written to the file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_fixture(dest: Path) -> None:
    """
    Generates a fixture directory structure for testing wiki prompts.

    Args:
        dest: The base destination directory where the fixture structure  and content will be created.

    Raises:
        SubprocessError: If any subprocess command (e.g., git operations)
            fails to execute successfully.
    """
    docs = dest / "docs"
    _write(docs / "schema.md", SCHEMA_MD)

    for filename, content in WIKI_PAGES.items():
        _write(docs / "wiki" / filename, content)

    for filename, (source_id, title) in PROCESSED_SOURCES.items():
        _write(
            docs / "sources" / filename,
            f"---\nsource: {source_id}\nprocessed: true\n---\n\n# {title}\n",
        )

    manifest_lines = []
    for filename, (source_id, title) in PROCESSED_SOURCES.items():
        covered_by = {
            "jira:INFRA-100": "docs/wiki/redis-cache.md",
            "jira:AUTH-200": "docs/wiki/auth-service.md",
            "design:infra-overview-v1": "docs/wiki/infrastructure-overview.md",
        }[source_id]
        manifest_lines.append(
            '{"source": "%s", "path": "docs/sources/%s", "title": "%s", '
            '"referenced_by": ["%s"], "updated": "2026-06-01T00:00:00Z", '
            '"update_sha": "0000000000000000000000000000000000000000", '
            '"status": "resolved", "covered_by": ["%s"]}' % (source_id, filename, title, covered_by, covered_by)
        )
    _write(docs / "source-manifest.jsonl", "\n".join(manifest_lines) + "\n")

    page_meta = {
        "redis-cache.md": ("Redis Cache", ["jira:INFRA-100"], ["Infrastructure Overview", "Auth Service"]),
        "auth-service.md": ("Auth Service", ["jira:AUTH-200"], ["Redis Cache", "Infrastructure Overview"]),
        "infrastructure-overview.md": (
            "Infrastructure Overview",
            ["design:infra-overview-v1"],
            ["Redis Cache", "Auth Service"],
        ),
    }
    catalog_lines = []
    for filename, (title, sources, links) in page_meta.items():
        links_json = ", ".join(f'"{link}"' for link in links)
        sources_json = ", ".join(f'"{s}"' for s in sources)
        catalog_lines.append(
            '{"path": "docs/wiki/%s", "title": "%s", "aliases": [], "links": [%s], '
            '"sources": [%s], "updated": "2026-06-03T00:00:00Z", "status": "resolved"}'
            % (filename, title, links_json, sources_json)
        )
    _write(docs / "catalog.jsonl", "\n".join(catalog_lines) + "\n")
    _write(docs / "log.jsonl", "")

    # New, unprocessed sources for the eval prompts to ingest.
    _write(docs / "sources" / "redis-eviction-fix.md", NEW_SOURCE_REDIS_EVICTION)
    _write(docs / "sources" / "ratelimit-design-doc.md", NEW_SOURCE_RATELIMIT_DESIGN)
    _write(docs / "sources" / "ratelimit-implementation-ticket.md", NEW_SOURCE_RATELIMIT_TICKET)
    _write(docs / "sources" / "ratelimit-slack-thread.md", NEW_SOURCE_RATELIMIT_SLACK)

    subprocess.run(["git", "init", "-q", "-b", "main", str(dest)], check=True)
    subprocess.run(["git", "-C", str(dest), "add", "-A"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(dest),
            "-c",
            "user.email=fixture@example.com",
            "-c",
            "user.name=Fixture",
            "commit",
            "-q",
            "-m",
            "Initial fixture wiki",
        ],
        check=True,
    )

    # Apply the "update to an already-covered source" mutation as a second
    # commit, so `source-delta` has a real prior revision on `main` to diff
    # against (eval 3 needs this — it's specifically testing the update path).
    _write(docs / "sources" / "jira-auth-200.md", UPDATED_SOURCE_AUTH_200)
    subprocess.run(["git", "-C", str(dest), "add", "-A"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(dest),
            "-c",
            "user.email=fixture@example.com",
            "-c",
            "user.name=Fixture",
            "commit",
            "-q",
            "-m",
            "AUTH-200: JWT expiry changed to 1h",
        ],
        check=True,
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: build_fixture.py <dest_dir>", file=sys.stderr)
        sys.exit(1)
    build_fixture(Path(sys.argv[1]))
    print(f"Fixture built at {sys.argv[1]}")
