import { describe, expect, test } from "bun:test";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  enginePath,
  githubSlug,
  normalizeSiteUrl,
  parsePythonVersion,
  patchConfig,
  preflight,
  pythonOk,
  readJson,
  run,
} from "../src/lib.ts";

describe("parsing", () => {
  test("python version", () => {
    expect(parsePythonVersion("Python 3.12.4")).toEqual([3, 12]);
    expect(parsePythonVersion("nope")).toBeNull();
    expect(pythonOk([3, 10])).toBe(true);
    expect(pythonOk([3, 9])).toBe(false);
    expect(pythonOk([4, 0])).toBe(true);
    expect(pythonOk(null)).toBe(false);
  });

  test("github slug from remotes", () => {
    expect(githubSlug("git@github.com:Nabwinsaud/khata.git")).toBe("Nabwinsaud/khata");
    expect(githubSlug("https://github.com/Nabwinsaud/khata.git\n")).toBe("Nabwinsaud/khata");
    expect(githubSlug("https://github.com/o/my.repo")).toBe("o/my.repo");
    expect(githubSlug("git@gitlab.com:o/r.git")).toBeNull();
  });

  test("site url", () => {
    expect(normalizeSiteUrl("acme.atlassian.net/")).toBe("https://acme.atlassian.net");
    expect(normalizeSiteUrl("https://acme.atlassian.net")).toBe("https://acme.atlassian.net");
  });
});

describe("patchConfig", () => {
  const base = {
    tracker: { type: "local", $examples: {} },
    vcs: { type: "local", base_branch: "main" },
    policy: { protected_paths: ["x/**"] },
  };

  test("defaults are safe: local tracker, auto-merge off, protected paths kept", () => {
    const c = patchConfig(base, { tracker: "local" });
    expect(c.tracker).toEqual({ type: "local" });
    expect(c.vcs).toEqual(base.vcs);
    expect(c.policy).toEqual({ protected_paths: ["x/**"], auto_merge_max_risk: "none" });
  });

  test("github sets tracker and vcs", () => {
    const c = patchConfig(base, { tracker: "github", githubRepo: "o/r" });
    expect(c.tracker).toEqual({ type: "github", repo: "o/r", ready_label: "factory:ready" });
    expect(c.vcs).toMatchObject({ type: "github", repo: "o/r", base_branch: "main" });
  });

  test("jira builds a jql that skips epics", () => {
    const c = patchConfig(base, {
      tracker: "jira",
      jira: { baseUrl: "https://a.atlassian.net", projectKey: "KAN" },
    });
    expect(c.tracker).toMatchObject({
      type: "jira",
      base_url: "https://a.atlassian.net",
      token_env: "JIRA_API_TOKEN",
    });
    expect((c.tracker as { jql: string }).jql).toContain(
      "project = KAN AND labels = factory AND issuetype != Epic",
    );
  });

  test("does not mutate input", () => {
    patchConfig(base, { tracker: "github", githubRepo: "o/r" });
    expect(base.tracker.type).toBe("local");
  });
});

describe("engine", () => {
  test("bundled or source engine scaffolds a go repo", () => {
    const dir = mkdtempSync(join(tmpdir(), "cf-"));
    run("git", ["init", "-q", "-b", "main"], dir);
    writeFileSync(join(dir, "go.mod"), "module example.com/x\n\ngo 1.22\n");
    const pf = preflight(dir);
    expect(pf.root).not.toBeNull();
    expect(pf.hasFactory).toBe(false);

    const res = run("python3", [join(enginePath(), "bin", "forgeline"), "init", "--json"], dir);
    expect(res.ok).toBe(true);
    const out = JSON.parse(res.stdout);
    expect(out.components[0]).toMatchObject({ lang: "go", area: "backend" });
    expect(readJson(join(dir, ".factory", "config.json")).policy).toBeDefined();
    expect(preflight(dir).hasFactory).toBe(true);
  });
});
