# Wiki Toolkit

AI skills that implement and maintain an [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — a
Raw/Wiki/Schema knowledge base kept current by routing every mutation through a reviewed PR.

## Install

```console
$ uv tool install wiki-toolkit
```

`init` scaffolds a wiki and drops a local copy of the skills into it (see
[implementation-history.md](docs/design/implementation-history.md)).

## The skill workflow

An agent (Claude Code or another skill-driven harness) operates the wiki through six skills,
each wrapping a handful of `wiki-toolkit` CLI commands plus the judgment a CLI alone can't
supply:

| Skill           | Purpose                                                               |
|-----------------|-----------------------------------------------------------------------|
| `ingest`        | Drive a new or updated source through the write gate into a wiki page |
| `source-update` | Refresh pages whose cited source changed fields, no new content       |
| `cross-linker`  | Weave a session's new pages into the existing knowledge graph         |
| `lint`          | Deterministic + semantic audit: structure, staleness, contradictions  |
| `maintain`      | Orchestrate `lint` → `source-update` → `ingest` as a periodic sweep   |
| `query`         | Answer questions from the compiled catalog, with citations            |

## The CLI underneath

The skills above are the intended day-to-day interface; the `wiki-toolkit` CLI is what they
call. Useful directly for scripting or debugging one step in isolation:

```console
$ wiki-toolkit doctor
$ wiki-toolkit source-scan --update
$ wiki-toolkit lint
$ wiki-toolkit build
$ wiki-toolkit propose-pr --pages docs/wiki/my-note.md --frame routine
```

`wiki-toolkit --help` lists every command:

| Command           | Purpose                                                           |
|-------------------|-------------------------------------------------------------------|
| `doctor`          | Non-mutating health check of the `docs/` structure and git clone  |
| `source-scan`     | Classify `docs/sources/` files as new, update, or duplicate       |
| `source-lint`     | Validate `docs/sources/` frontmatter and report uncovered sources |
| `source-coverage` | Show which sources are cited by at least one wiki note            |
| `source-dedupe`   | Suggest which file to keep among duplicate sources                |
| `source-delta`    | Diff a source's current content against its last-known revision   |
| `source-snapshot` | Write a new Raw snapshot for a source's comments/fields mutation  |
| `lint`            | Validate wiki note frontmatter, tags, and source links            |
| `build`           | Regenerate `docs/catalog.jsonl` from the current wiki notes       |
| `search-catalog`  | Search the catalog by title or path                               |
| `propose-pr`      | Stage a wiki change as a local git branch + commit (never pushes) |
| `log`             | Append a structured entry to `docs/log.jsonl`                     |

## Documentation

Full docs, including a walkthrough tutorial, how-to guides, and the command reference, are at
<https://callowayproject.github.io/wiki_toolkit>.

## Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for how to get started. This project follows a
[Code of Conduct](CODE_OF_CONDUCT.md).

## License

See [LICENSE](LICENSE).
