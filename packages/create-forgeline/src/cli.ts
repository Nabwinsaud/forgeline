#!/usr/bin/env node
// create-forgeline: set up Forgeline in the current repo in one go.
import { join } from "node:path";
import { parseArgs } from "node:util";
import * as p from "@clack/prompts";
import pkg from "../package.json" with { type: "json" };
import {
  type Answers,
  enginePath,
  gitPushAuthOk,
  normalizeSiteUrl,
  patchConfig,
  preflight,
  pythonOk,
  readJson,
  run,
  type Tracker,
  useGhCredentials,
  writeJson,
} from "./lib.ts";

const HELP = `create-forgeline ${pkg.version}

Set up Forgeline (agentic software factory for Claude Code) in the current git repo.

Usage
  npm create forgeline          or   bunx create-forgeline
  npx create-forgeline [options]

Options
  -y, --yes             accept defaults, no questions (local tracker, auto-merge off)
  --tracker <type>      local | github | jira | linear
  --no-plugin           don't install the Claude Code plugin
  --skip-gate           don't run .factory/checks.sh at the end
  -v, --version         print version
  -h, --help            show this help
`;

function bail(msg: string): never {
  p.cancel(msg);
  process.exit(1);
}

function answer<T>(value: T): Exclude<T, symbol> {
  if (p.isCancel(value)) bail("Cancelled. Nothing was changed after the last step shown.");
  return value as Exclude<T, symbol>;
}

async function main(): Promise<void> {
  const { values: o } = parseArgs({
    options: {
      yes: { type: "boolean", short: "y" },
      tracker: { type: "string" },
      plugin: { type: "boolean", default: true },
      "no-plugin": { type: "boolean" },
      "skip-gate": { type: "boolean" },
      version: { type: "boolean", short: "v" },
      help: { type: "boolean", short: "h" },
    },
    allowNegative: true,
  });
  if (o.help) return void console.log(HELP);
  if (o.version) return void console.log(pkg.version);
  const yes = !!o.yes;
  const wantPlugin = o.plugin && !o["no-plugin"];

  p.intro(`create-forgeline ${pkg.version}`);

  // 1. Check the machine and the repo.
  const s = p.spinner();
  s.start("Checking your repo and tools");
  const pf = preflight(process.cwd());
  s.stop("Checked");
  if (!pf.root) bail("Not inside a git repo. Run `git init` first (Forgeline works on git branches).");
  if (!pythonOk(pf.python)) {
    bail(
      "Python 3.10+ is needed for the Forgeline engine. macOS: `xcode-select --install` or `brew install python`.",
    );
  }
  if (pf.hasFactory) bail(".factory/ already exists here. Edit it directly, or delete it to start over.");
  p.log.info(
    [
      `repo     ${pf.root}`,
      `branch   ${pf.branch ?? "(detached)"}${pf.clean ? "" : "  (uncommitted changes)"}`,
      `python   ${pf.python?.join(".")}`,
      `github   ${pf.githubRepo ?? "no GitHub remote"}${pf.githubRepo && !pf.ghAuthed ? "  (gh not logged in)" : ""}`,
      `claude   ${pf.claude ? "found" : "not found (needed to run the factory)"}`,
    ].join("\n"),
  );
  if (!pf.clean && !yes) {
    const go = answer(
      await p.confirm({ message: "You have uncommitted changes. Continue anyway?", initialValue: false }),
    );
    if (!go) bail("Commit or stash your changes, then run again.");
  }

  // Several GitHub accounts on one machine: gh can be logged in as the right one while git's saved
  // credentials belong to another, and the factory's pushes then fail with "Repository not found".
  if (pf.githubRepo && pf.ghAuthed && !gitPushAuthOk(pf.root)) {
    p.log.warn("git can't push to origin with its saved login, but gh can (different GitHub account?).");
    const fix =
      yes ||
      answer(await p.confirm({ message: "Make git use gh's login for this repo only?", initialValue: true }));
    if (fix) {
      useGhCredentials(pf.root);
      p.log.success(
        gitPushAuthOk(pf.root)
          ? "Fixed: git now uses gh's login here."
          : "Set, but push still fails. Check `gh auth status`.",
      );
    }
  }

  // 2. Ask where tickets come from.
  const github = pf.githubRepo && pf.ghAuthed ? pf.githubRepo : null;
  let tracker = (o.tracker as Tracker | undefined) ?? "local";
  if (!["local", "github", "jira", "linear"].includes(tracker)) bail(`Unknown tracker: ${tracker}`);
  if (!yes && !o.tracker) {
    tracker = answer(
      await p.select<Tracker>({
        message: "Where do your tickets live?",
        initialValue: "local",
        options: [
          { value: "local", label: "Local", hint: "forgeline ticket add, good for trying it out" },
          {
            value: "github",
            label: "GitHub Issues",
            hint: github ? `label factory:ready on ${github}` : "needs a GitHub remote + gh login",
            disabled: !github,
          },
          { value: "jira", label: "Jira", hint: "needs an API token in env vars" },
          { value: "linear", label: "Linear", hint: "needs LINEAR_API_KEY" },
        ],
      }),
    );
  }
  const answers: Answers = { tracker, githubRepo: github, autoMergeMaxRisk: "none" };
  if (tracker === "jira" && !yes) {
    const site = answer(await p.text({ message: "Jira site", placeholder: "your-site.atlassian.net" }));
    const key = answer(
      await p.text({
        message: "Jira project key",
        placeholder: "APP",
        validate: (v) => (/^[A-Z][A-Z0-9]+$/.test(v ?? "") ? undefined : "Uppercase key, like APP or KAN"),
      }),
    );
    answers.jira = { baseUrl: normalizeSiteUrl(site), projectKey: key };
  }
  if (tracker === "linear" && !yes) {
    answers.linearTeam = answer(await p.text({ message: "Linear team key", placeholder: "APP" }));
  }

  // 3. Scaffold with the engine, then apply the answers.
  s.start("Writing .factory/ and rule packs");
  const engine = enginePath();
  const init = run(
    "python3",
    [join(engine, "bin", "forgeline"), "init", "--json", "--tracker", tracker],
    pf.root,
  );
  if (!init.ok) {
    s.stop("forgeline init failed");
    bail(init.stderr.trim() || init.stdout.trim());
  }
  const result = JSON.parse(init.stdout) as { components: { dir: string; lang: string; area: string }[] };
  const cfgPath = join(pf.root, ".factory", "config.json");
  writeJson(cfgPath, patchConfig(readJson(cfgPath), answers));
  s.stop("Wrote .factory/");
  p.log.info(
    result.components.length
      ? `Detected: ${result.components.map((c) => `${c.lang} in ${c.dir} (${c.area})`).join(", ")}`
      : "No stack detected. Add your build and test commands to .factory/checks.sh.",
  );

  if (tracker === "github" && github) {
    run(
      "gh",
      [
        "label",
        "create",
        "factory:ready",
        "--repo",
        github,
        "--color",
        "0E8A16",
        "--description",
        "Forgeline picks this up",
        "--force",
      ],
      pf.root,
    );
    p.log.success("GitHub label factory:ready is ready. Add it to an issue to hand it to the factory.");
  }

  // 4. Run the gate once so the user knows it is green before any agent touches it.
  if (!o["skip-gate"]) {
    s.start("Running the gate (.factory/checks.sh)");
    const gate = run("bash", [join(pf.root, ".factory", "checks.sh")], pf.root, {
      FACTORY_BASE: pf.branch ?? "main",
    });
    if (gate.ok) s.stop("Gate passes");
    else {
      s.stop("Gate fails");
      p.log.warn(
        `Fix this before running the factory, or nothing can merge:\n${(gate.stdout + gate.stderr).trim().split("\n").slice(-12).join("\n")}`,
      );
    }
  }

  // 5. Claude Code plugin: agents, hooks and /forgeline:* commands.
  if (wantPlugin && pf.claude) {
    const install =
      yes ||
      answer(
        await p.confirm({ message: "Install the Forgeline plugin in Claude Code?", initialValue: true }),
      );
    if (install) {
      s.start("Installing the Claude Code plugin");
      run("claude", ["plugin", "marketplace", "add", "Nabwinsaud/forgeline"]);
      const res = run("claude", ["plugin", "install", "forgeline@forgeline"]);
      s.stop(res.ok ? "Plugin installed" : "Plugin install failed (run /plugin install forgeline@forgeline)");
    }
  }

  // 6. What to do next.
  const next = [
    "1. Write your business rules in .factory/domain.md (agents read it before every step)",
    "2. Check .factory/config.json. Auto-merge is off until you trust it.",
  ];
  if (tracker === "jira")
    next.push("3. export JIRA_EMAIL=... JIRA_API_TOKEN=...  (never put tokens in config)");
  if (tracker === "linear") next.push("3. export LINEAR_API_KEY=...");
  next.push(
    `${next.length + 1}. Commit: git add .factory .claude && git commit -m "chore: add Forgeline"`,
    tracker === "local"
      ? `${next.length + 2}. forgeline ticket add "Add a /health endpoint", then /forgeline:run in Claude Code`
      : `${next.length + 2}. Label a small ticket for the factory, then /forgeline:run in Claude Code`,
  );
  p.note(next.join("\n"), "Next");
  p.outro("Forgeline is set up.");
}

main().catch((err: unknown) => bail(err instanceof Error ? err.message : String(err)));
