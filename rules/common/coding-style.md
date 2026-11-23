# Coding style

- Match the existing code in the repo before any generic convention. Consistency wins.
- Run the repo's formatter and linter; never hand-format against them.
- Name things for what they are in the domain. No `data`, `info`, `manager`, `helper`, `utils`
  as the whole name.
- Functions do one thing. If a name needs "and", split it.
- Prefer early returns over nested conditionals.
- Keep functions short enough to read without scrolling; extract when a block needs a comment
  to explain what it does.
- No dead code, commented-out code, or debug prints in commits.
- Comments explain *why*, not *what*. Delete comments that restate the code.
- No magic numbers or strings in logic; use named constants.
- Prefer immutable data and pure functions for business rules; push I/O to the edges.
- Validate input at boundaries; trust typed data inside.
- Handle every error: return it with context, handle it, or document why it is ignored.
- No speculative abstraction: no interface, base class, option or config without a current use.
- Do not duplicate an existing helper; search the repo first.
- Do not add a dependency for something a few lines of code or the standard library does.
- New dependencies: pinned, maintained, licence-compatible, mentioned in the PR notes.
- Keep diffs focused on the task. No drive-by reformatting or renames in unrelated files.
- TODOs need a reason and a ticket reference, and never stand in for behavior the spec requires.
