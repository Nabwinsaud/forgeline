// Everything the wizard needs that can be tested without prompts.
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export type Tracker = "local" | "github" | "jira" | "linear";

export interface RunResult {
  ok: boolean;
  code: number;
  stdout: string;
  stderr: string;
}

export function run(
  cmd: string,
  args: string[],
  cwd?: string,
  env?: Record<string, string>,
  timeoutMs?: number,
): RunResult {
  const p = spawnSync(cmd, args, {
    cwd,
    encoding: "utf8",
    env: { ...process.env, ...env },
    timeout: timeoutMs,
  });
  if (p.error) return { ok: false, code: -1, stdout: "", stderr: String(p.error.message) };
  return { ok: p.status === 0, code: p.status ?? -1, stdout: p.stdout ?? "", stderr: p.stderr ?? "" };
}

export function has(cmd: string): boolean {
  return run(cmd, ["--version"]).ok;
}

/** "Python 3.12.4" -> [3, 12]. */
export function parsePythonVersion(text: string): [number, number] | null {
  const m = /Python (\d+)\.(\d+)/.exec(text);
  return m ? [Number(m[1]), Number(m[2])] : null;
}

export function pythonOk(version: [number, number] | null): boolean {
  return !!version && (version[0] > 3 || (version[0] === 3 && version[1] >= 10));
}

/** git@github.com:o/r.git, https://github.com/o/r(.git) -> "o/r". Other hosts -> null. */
export function githubSlug(remoteUrl: string): string | null {
  const m = /github\.com[:/]([\w.-]+)\/([\w.-]+?)(?:\.git)?\/?$/.exec(remoteUrl.trim());
  return m ? `${m[1]}/${m[2]}` : null;
}

export interface Preflight {
  root: string | null;
  branch: string | null;
  clean: boolean;
  python: [number, number] | null;
  githubRepo: string | null;
  ghAuthed: boolean;
  claude: boolean;
  hasFactory: boolean;
}

export function preflight(cwd: string): Preflight {
  const root = run("git", ["rev-parse", "--show-toplevel"], cwd);
  const r = root.ok ? root.stdout.trim() : null;
  const py = run("python3", ["--version"]);
  const remote = r ? run("git", ["remote", "get-url", "origin"], r) : null;
  return {
    root: r,
    branch: r ? run("git", ["branch", "--show-current"], r).stdout.trim() || null : null,
    clean: r ? run("git", ["status", "--porcelain"], r).stdout.trim() === "" : false,
    python: parsePythonVersion(py.stdout + py.stderr),
    githubRepo: remote?.ok ? githubSlug(remote.stdout) : null,
    ghAuthed: run("gh", ["auth", "status"]).ok,
    claude: has("claude"),
    hasFactory: !!r && existsSync(join(r, ".factory", "config.json")),
  };
}

/** The Python engine: bundled in the npm package, or the repo root when running from source. */
export function enginePath(): string {
  if (process.env.FORGELINE_ENGINE) return process.env.FORGELINE_ENGINE;
  const here = dirname(fileURLToPath(import.meta.url));
  for (const candidate of [join(here, "..", "engine"), join(here, "..", "..", "..")]) {
    if (existsSync(join(candidate, "bin", "forgeline"))) return candidate;
  }
  throw new Error("Forgeline engine not found. Reinstall create-forgeline.");
}

export interface Answers {
  tracker: Tracker;
  githubRepo?: string | null;
  jira?: { baseUrl: string; projectKey: string };
  linearTeam?: string;
  autoMergeMaxRisk?: "none" | "low";
}

type Json = Record<string, unknown>;

/** Apply wizard answers to the config written by `forgeline init`. Pure. */
export function patchConfig(cfg: Json, a: Answers): Json {
  const out: Json = structuredClone(cfg);
  const policy = (out.policy as Json) ?? {};
  out.policy = { ...policy, auto_merge_max_risk: a.autoMergeMaxRisk ?? "none" };
  const vcs = (out.vcs as Json) ?? {};
  if (a.githubRepo) {
    out.vcs = { ...vcs, type: "github", repo: a.githubRepo, merge_method: "squash" };
  }
  const statusMap = { in_progress: "In Progress", in_review: "In Review", blocked: "Blocked", done: "Done" };
  switch (a.tracker) {
    case "local":
      out.tracker = { type: "local" };
      break;
    case "github":
      out.tracker = { type: "github", repo: a.githubRepo, ready_label: "factory:ready" };
      break;
    case "jira": {
      const key = a.jira?.projectKey ?? "APP";
      out.tracker = {
        type: "jira",
        base_url: a.jira?.baseUrl ?? "https://your-site.atlassian.net",
        jql: `project = ${key} AND labels = factory AND issuetype != Epic AND status = "To Do" ORDER BY rank`,
        status_map: statusMap,
        email_env: "JIRA_EMAIL",
        token_env: "JIRA_API_TOKEN",
      };
      break;
    }
    case "linear":
      out.tracker = {
        type: "linear",
        team_key: a.linearTeam ?? "APP",
        ready_state: "Todo",
        label: "factory",
        status_map: statusMap,
      };
      break;
  }
  return out;
}

export function readJson(path: string): Json {
  return JSON.parse(readFileSync(path, "utf8")) as Json;
}

export function writeJson(path: string, data: Json): void {
  writeFileSync(path, `${JSON.stringify(data, null, 2)}\n`);
}

export function normalizeSiteUrl(input: string): string {
  const s = input.trim().replace(/\/+$/, "");
  return /^https?:\/\//.test(s) ? s : `https://${s}`;
}

/** True when a failed push looks like "git is logged in as someone without access to this repo". */
export function looksLikeWrongAccount(stderr: string): boolean {
  return /repository not found|permission to .* denied|403|authentication failed|could not read username/i.test(
    stderr,
  );
}

/**
 * Can plain `git push` reach origin? A dry run still authenticates, so it catches the case where gh is
 * logged in as one GitHub account but git's saved credentials belong to another.
 */
export function gitPushAuthOk(root: string): boolean {
  const res = run(
    "git",
    ["push", "--dry-run", "--porcelain", "origin", "HEAD"],
    root,
    { GIT_TERMINAL_PROMPT: "0" },
    20_000,
  );
  return res.ok || !looksLikeWrongAccount(res.stderr);
}

/** Make git use gh's login for github.com, in this repo only. */
export function useGhCredentials(root: string): void {
  run("git", ["config", "--local", "--replace-all", "credential.https://github.com.helper", ""], root);
  run(
    "git",
    ["config", "--local", "--add", "credential.https://github.com.helper", "!gh auth git-credential"],
    root,
  );
}
