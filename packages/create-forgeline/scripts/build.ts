// Build: bundle the CLI for Node, and copy the Python engine next to it so one npm version
// always ships one matching engine version.
import { chmod, cp, rm } from "node:fs/promises";
import { join } from "node:path";

const pkg = join(import.meta.dir, "..");
const repo = join(pkg, "..", "..");

await rm(join(pkg, "dist"), { recursive: true, force: true });
const out = await Bun.build({
  entrypoints: [join(pkg, "src", "cli.ts")],
  outdir: join(pkg, "dist"),
  target: "node",
  format: "esm",
  minify: false,
});
if (!out.success) {
  for (const log of out.logs) console.error(log);
  process.exit(1);
}
await chmod(join(pkg, "dist", "cli.js"), 0o755);

const engine = join(pkg, "engine");
await rm(engine, { recursive: true, force: true });
for (const dir of ["bin", "forgeline", "defaults", "templates", "rules"]) {
  await cp(join(repo, dir), join(engine, dir), {
    recursive: true,
    filter: (src) => !src.includes("__pycache__"),
  });
}
console.log("built dist/cli.js and engine/");
