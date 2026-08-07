# Wiki Toolkit

AI skills and helper tools that implement and maintain an [LLM Wiki](https://karpathy.bearblog.dev/llm-wiki/) — a
Raw/Wiki/Schema knowledge base kept current by routing every mutation through a reviewed PR.

## Install

```console
$ uv tool install wiki-toolkit
```

## Quick look

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
