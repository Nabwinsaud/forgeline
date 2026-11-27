"""Domain packs: shareable starter rules for a kind of product (money, auth, api, web-app...).

A pack is a folder:
  pack.json    {"name", "description", "reviewer": {"name", "model"}}   (reviewer optional)
  domain.md    rules appended to .factory/domain.md
  reviewer.md  a domain reviewer prompt, run beside the other reviewers   (optional)
  checks.sh    a snippet added to the gate; it should only judge lines the branch adds  (optional)

Built-in packs live in templates/packs/. Any folder or git URL with the same layout works too, so
people can share packs for their own industries. Re-adding a pack updates it in place.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import config
from .util import TEMPLATES_DIR, FactoryError, load_json, write_json

BUILTIN = TEMPLATES_DIR / "packs"


def available() -> list[dict]:
    out = []
    for d in sorted(BUILTIN.iterdir()) if BUILTIN.is_dir() else []:
        meta = load_json(d / "pack.json", {}) or {}
        if meta:
            out.append({"name": meta.get("name", d.name), "description": meta.get("description", ""),
                        "checks": (d / "checks.sh").exists(), "reviewer": bool(meta.get("reviewer"))})
    return out


def _resolve(source: str) -> tuple[Path, tempfile.TemporaryDirectory | None]:
    if (BUILTIN / source / "pack.json").exists():
        return BUILTIN / source, None
    p = Path(source).expanduser()
    if (p / "pack.json").exists():
        return p, None
    if re.match(r"^(https://|git@)", source):
        tmp = tempfile.TemporaryDirectory(prefix="forgeline-pack-")
        proc = subprocess.run(["git", "clone", "--depth", "1", "--quiet", source, tmp.name],
                              capture_output=True, text=True)
        if proc.returncode != 0 or not (Path(tmp.name) / "pack.json").exists():
            tmp.cleanup()
            raise FactoryError(f"could not get a pack from {source}: {proc.stderr.strip()[:300] or 'no pack.json'}")
        return Path(tmp.name), tmp
    names = ", ".join(p["name"] for p in available())
    raise FactoryError(f"no pack called {source!r}. Built in: {names}. Or pass a folder or git URL.")


def _md_block(name: str, body: str) -> str:
    return f"<!-- pack:{name} -->\n{body.strip()}\n<!-- /pack:{name} -->"


def _sh_block(name: str, body: str) -> str:
    return f"# >>> pack:{name}\n{body.strip()}\n# <<< pack:{name}"


def _replace_or_insert(text: str, start: str, end: str, block: str, before: list[str]) -> str:
    pat = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if pat.search(text):
        return pat.sub(lambda _: block, text)
    for marker in before:
        i = text.find(marker)
        if i != -1:
            return text[:i] + block + "\n\n" + text[i:]
    return text.rstrip() + "\n\n" + block + "\n"


def _remove(text: str, start: str, end: str) -> str:
    return re.sub(r"\n*" + re.escape(start) + r".*?" + re.escape(end) + r"\n?", "\n", text, flags=re.S)


def add(source: str) -> dict:
    src, tmp = _resolve(source)
    try:
        meta = load_json(src / "pack.json", {}) or {}
        name = re.sub(r"[^a-z0-9-]", "-", (meta.get("name") or src.name).lower())
        ddir = config.domain_dir()
        changed = []

        if (src / "domain.md").exists():
            path = ddir / "domain.md"
            text = path.read_text() if path.exists() else "# Domain\n"
            path.write_text(_replace_or_insert(text, f"<!-- pack:{name} -->", f"<!-- /pack:{name} -->",
                                               _md_block(name, (src / "domain.md").read_text()), []))
            changed.append("domain.md")

        if (src / "checks.sh").exists():
            path = ddir / "checks.sh"
            if not path.exists():
                raise FactoryError("no .factory/checks.sh. Run `forgeline init` first.")
            text = path.read_text()
            path.write_text(_replace_or_insert(text, f"# >>> pack:{name}", f"# <<< pack:{name}",
                                               _sh_block(name, (src / "checks.sh").read_text()),
                                               ["# --- Your business checks go here", "printf '\\ngate: all checks passed"]))
            changed.append("checks.sh")

        rev = meta.get("reviewer")
        if rev and (src / "reviewer.md").exists():
            rname = re.sub(r"[^a-z0-9-]", "-", rev.get("name", name).lower())
            (ddir / "reviewers").mkdir(exist_ok=True)
            shutil.copy2(src / "reviewer.md", ddir / "reviewers" / f"{rname}.md")
            cfg_path = ddir / "config.json"
            cfg = load_json(cfg_path)
            revs = [r for r in cfg.get("domain_reviewers", []) if r.get("name") != rname]
            revs.append({"name": rname, "prompt": f"reviewers/{rname}.md", "model": rev.get("model", "sonnet"),
                         "pack": name})
            cfg["domain_reviewers"] = revs
            write_json(cfg_path, cfg)
            changed += [f"reviewers/{rname}.md", "config.json"]

        return {"pack": name, "description": meta.get("description", ""), "changed": changed,
                "checks": (src / "checks.sh").read_text() if (src / "checks.sh").exists() else ""}
    finally:
        if tmp:
            tmp.cleanup()


def remove(name: str) -> list[str]:
    ddir = config.domain_dir()
    changed = []
    for fname, start, end in (("domain.md", f"<!-- pack:{name} -->", f"<!-- /pack:{name} -->"),
                              ("checks.sh", f"# >>> pack:{name}", f"# <<< pack:{name}")):
        path = ddir / fname
        if path.exists() and start in path.read_text():
            path.write_text(_remove(path.read_text(), start, end))
            changed.append(fname)
    cfg_path = ddir / "config.json"
    cfg = load_json(cfg_path)
    keep = [r for r in cfg.get("domain_reviewers", []) if r.get("pack") != name]
    for r in cfg.get("domain_reviewers", []):
        if r.get("pack") == name:
            (ddir / r["prompt"]).unlink(missing_ok=True)
            changed.append(r["prompt"])
    if len(keep) != len(cfg.get("domain_reviewers", [])):
        cfg["domain_reviewers"] = keep
        write_json(cfg_path, cfg)
        changed.append("config.json")
    if not changed:
        raise FactoryError(f"pack {name!r} isn't installed here")
    return changed


def installed() -> list[str]:
    path = config.domain_dir() / "domain.md"
    text = path.read_text() if path.exists() else ""
    sh = (config.domain_dir() / "checks.sh")
    text += sh.read_text() if sh.exists() else ""
    return sorted(set(re.findall(r"(?:<!-- |# >>> )pack:([a-z0-9-]+)", text)))
