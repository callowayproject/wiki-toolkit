# Job Stories
These are various scenarios, motivations, and desired outcomes.

## Roles

- **we/us**: Our team that is creating and deploying infrastructure for an app team.
- **app team**: A team of application developers, testers, and users.

## Scenarios

### Reading the wiki

1. **WHEN** the app team hands us a design document, we want to know what infrastructure it implies and why, so we can scope the work without having to reread the whole doc every time someone asks.
2. **WHEN** someone new to the repo needs to change infrastructure they didn't build, they want to understand why it exists and who to ask about it, so they can make the change without breaking anything they don't understand.
3. **WHEN** we're troubleshooting an incident, we want to quickly find the documentation for the involved infrastructure so we can understand its purpose and constraints without paging the person who built it.
4. **WHEN** we read a claim in the docs, we want to trace it back to the source that justified it, so we can judge whether it's still accurate.

### Keeping the wiki in sync

1. **WHEN** we make a change to the infrastructure and a pull request is merged into the main branch, we want the documentation to be updated automatically.
2. **WHEN** an external pull request (e.g., Dependabot, Renovate) changes infrastructure, we want the documentation to reflect that change as well, so the documentation doesn't silently drift just because a human didn't author the diff.
3. **WHEN** infrastructure is removed or replaced, we want its documentation retired or updated, so the wiki doesn't accumulate stale references that mislead the next reader.
4. **WHEN** we're reviewing a pull request that changes infrastructure, we want to see whether the documentation has kept pace, so we can catch drift before it merges rather than after.

### Traceability and trust

1. **WHEN** a ticket, chat thread, or design doc is the actual reason behind an infrastructure change, we want that source traceable from the change itself, so we can answer "why does this look like this" without hunting through other systems.
2. **WHEN** an external, less-trusted source (a ticket body, a PR description) feeds into whatever writes our docs, we want assurance it can't be used to sneak unreviewed changes into the repo, so the automation doesn't become a way in for someone who isn't a reviewer.
