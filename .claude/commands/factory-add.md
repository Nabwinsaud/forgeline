---
description: Add a ticket to a project's local tracker (for trying the factory without GitHub/Jira/Linear).
argument-hint: "<project> <title> [-- body]"
---

Turn `$ARGUMENTS` into a well-formed ticket and add it:

`bin/factory ticket add <project> "<title>" --body "<body>"`

Write the body as: problem, desired behavior, acceptance hints, out of scope. Keep the user's
intent; do not invent requirements. Only works when the project's tracker type is `local`;
otherwise tell the user to create the ticket in their tracker with the ready label/state.
