"""Evidence references in memory topic files, and a verifier for them.

A memory's YAML frontmatter may carry ``evidence: [{ref, sha256}]``. The
verifier checks that each referent still exists and, where a digest was
recorded, is unchanged. ``intact`` means the evidence is unchanged since it was
cited. It never means the memory is true.

Spec: docs/superpowers/specs/2026-10-14-evidence-references.md.
CLI: ``python -m yanantin.evidence check <memory dir>`` and
``python -m yanantin.evidence pin <ref>``.
"""

from __future__ import annotations

import configparser
import hashlib
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

FAILING = ("changed", "missing")


class Unavailable(Exception):
    """The store could not be asked."""


@dataclass(frozen=True)
class Result:
    file: str
    ref: str
    status: str
    note: str = ""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}
    data = yaml.safe_load(text[4:end])
    return data if isinstance(data, dict) else {}


def _slugs(value) -> list[str]:
    values = value if isinstance(value, list) else [value] if value else []
    return [str(v).strip().removeprefix("[[").removesuffix("]]").removesuffix(".md") for v in values]


def _default_repos() -> Path:
    return Path(os.environ.get("YANANTIN_REPOS") or Path.home() / "projects")


def khipumaq_fetcher(repos: Path):
    """Episode lookup through khipumaq's own config file, found where khipumaq looks:
    $KHIPUMAQ_CONFIG alone if set, else XDG config, else its checkout under ``repos``.
    Raises Unavailable if there is none or it can't connect."""
    if os.environ.get("KHIPUMAQ_CONFIG"):
        candidates = [Path(os.environ["KHIPUMAQ_CONFIG"])]
    else:
        xdg = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
        candidates = [xdg / "khipumaq" / "db-config.ini",
                      repos / "khipumaq" / "config" / "db-config.ini"]
    path = next((p for p in candidates if p.exists()), None)
    if path is None:
        raise Unavailable("no khipumaq config; looked in " + ", ".join(map(str, candidates)))
    parser = configparser.ConfigParser()
    parser.read(path)
    cfg = parser["database"]
    try:
        from yanantin.infra.config import get_database

        db = get_database(host=f"http://{cfg['host']}:{cfg['port']}", db_name=cfg["database"],
                          username=cfg["user_name"], password=cfg["user_password"])
        episodes = db.collection("episodes")
        episodes.count()
    except Exception as exc:
        raise Unavailable(f"khipumaq unreachable: {exc}") from exc
    return episodes.get


def _resolve(ref: str, repos: Path, memory_dir: Path, fetch_episode) -> bytes | None:
    """Return the bytes the digest covers (b"" when the scheme needs none), None if missing."""
    scheme, _, rest = ref.partition(":")
    if scheme == "git":
        repo, _, target = rest.partition("@")
        commit, _, path = target.partition(":")
        if not (repos / repo / ".git").exists():
            raise Unavailable(f"no repository {repos / repo}")
        git = lambda *a: subprocess.run(("git", "-C", str(repos / repo), *a), capture_output=True)
        if not path:
            return b"" if git("cat-file", "-e", f"{commit}^{{commit}}").returncode == 0 else None
        shown = git("show", f"{commit}:{path}")
        return shown.stdout if shown.returncode == 0 else None
    if scheme == "khipumaq":
        episode = fetch_episode()(rest)
        if episode is None:
            return None
        return f"{episode.get('user_message') or ''}\0{episode.get('response') or ''}".encode()
    if scheme == "memory":
        target = memory_dir / f"{rest}.md"
        return target.read_bytes() if target.exists() else None
    raise KeyError(scheme)


def _needs_digest(ref: str) -> bool:
    return not (ref.startswith("git:") and ":" not in ref.partition("@")[2])


class _Lazy:
    """Build the khipumaq fetcher at most once, and only if a khipumaq ref appears."""

    def __init__(self, fetch_episode, repos: Path):
        self._fetch, self._error, self._repos = fetch_episode, None, repos

    def __call__(self):
        if self._fetch is None and self._error is None:
            try:
                self._fetch = khipumaq_fetcher(self._repos)
            except Unavailable as exc:
                self._error = exc
        if self._error is not None:
            raise self._error
        return self._fetch


def check_dir(memory_dir, repos=None, fetch_episode=None) -> list[Result]:
    memory_dir = Path(memory_dir)
    repos = Path(repos) if repos else _default_repos()
    fetch = _Lazy(fetch_episode, repos)
    files = {p: frontmatter(p) for p in sorted(memory_dir.glob("*.md"))}
    relation = {}
    for meta in files.values():
        for slug in _slugs(meta.get("supersedes")):
            relation.setdefault(slug, "superseded")
        for slug in _slugs(meta.get("retracts")):
            relation[slug] = "withdrawn"
    results = []
    for path, meta in files.items():
        for item in meta.get("evidence") or []:
            ref, pinned = str(item.get("ref", "")), item.get("sha256")
            note = relation.get(ref.removeprefix("memory:"), "") if ref.startswith("memory:") else ""
            try:
                data = _resolve(ref, repos, memory_dir, fetch)
            except KeyError:
                status = "unknown"
            except Unavailable:
                status = "unavailable"
            else:
                if data is None:
                    status, note = "missing", ""
                elif not _needs_digest(ref):
                    status = "intact"
                elif not pinned:
                    status = "unpinned"
                else:
                    status = "intact" if _sha(data) == str(pinned) else "changed"
            results.append(Result(path.name, ref, status, note))
    return results


def pin(ref: str, repos=None, memory_dir=None, fetch_episode=None) -> dict:
    """The evidence entry for ``ref`` as it stands now."""
    repos = Path(repos) if repos else _default_repos()
    data = _resolve(ref, repos, Path(memory_dir or "."), _Lazy(fetch_episode, repos))
    if data is None:
        raise LookupError(f"{ref} does not resolve")
    return {"ref": ref, "sha256": _sha(data)} if _needs_digest(ref) else {"ref": ref}


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="python -m yanantin.evidence")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="check every evidence reference in a memory directory")
    check.add_argument("memory_dir")
    check.add_argument("--repos")
    pinner = sub.add_parser("pin", help="print the evidence entry for a reference")
    pinner.add_argument("ref")
    pinner.add_argument("--repos")
    pinner.add_argument("--memory-dir")
    args = parser.parse_args(argv)
    if args.command == "pin":
        try:
            entry = pin(args.ref, args.repos, args.memory_dir)
        except (Unavailable, LookupError, KeyError) as exc:
            print(f"cannot pin {args.ref}: {exc}", file=sys.stderr)
            return 2
        print(yaml.safe_dump([entry], sort_keys=False), end="")
        return 0
    results = check_dir(args.memory_dir, args.repos)
    for r in results:
        label = "evidence intact" if r.status == "intact" else r.status
        print(f"{label}{f' ({r.note})' if r.note else ''}  {r.file}  {r.ref}")
    return 1 if any(r.status in FAILING for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
