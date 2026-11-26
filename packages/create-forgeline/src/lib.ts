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

export function run(cmd: string, args: string[], cwd?: string, env?: Record<string, string>): RunResult {
  const p = spawnSync(cmd, args, { cwd, encoding: "utf8", env: { ...process.env, ...env } });
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
