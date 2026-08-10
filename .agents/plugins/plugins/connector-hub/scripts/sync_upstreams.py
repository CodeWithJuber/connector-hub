#!/usr/bin/env python3
"""Synchronize approved ForgeKit and Hikmah Stack source repositories.

Data sources:
https://github.com/CodeWithJuber/forgekit
https://github.com/CodeWithJuber/hikmah-stack
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Final
from urllib.parse import urlparse

SOURCES: Final[dict[str, str]] = {
    "forgekit": "https://github.com/CodeWithJuber/forgekit.git",
    "hikmah-stack": "https://github.com/CodeWithJuber/hikmah-stack.git",
}
ALLOWED_HOST: Final = "github.com"
LOG = logging.getLogger("connector_hub.sync")


class SyncError(RuntimeError):
    """An actionable source synchronization failure."""


def validate_source(name: str, url: str) -> None:
    """Reject unapproved names, transports, hosts, and repository paths."""
    expected = SOURCES.get(name)
    parsed = urlparse(url)
    if expected != url:
        raise SyncError(f"Unapproved source for {name}: expected {expected!r}")
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST:
        raise SyncError(f"Source {name} must use HTTPS on {ALLOWED_HOST}")
    if parsed.username or parsed.password or parsed.port:
        raise SyncError(f"Source {name} must not embed credentials or a custom port")


def run_git(args: list[str], *, cwd: Path | None = None, timeout: int = 120) -> str:
    """Run Git without a shell and return bounded diagnostic output."""
    env = os.environ.copy()
    env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1"})
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, env=env, check=False, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise SyncError(f"git {' '.join(args[:2])} timed out after {timeout}s") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()[-2000:]
        raise SyncError(f"git {' '.join(args[:2])} failed: {detail}")
    return result.stdout.strip()


def clone_with_retry(url: str, destination: Path, ref: str | None, attempts: int = 3) -> None:
    last_error: SyncError | None = None
    for attempt in range(1, attempts + 1):
        shutil.rmtree(destination, ignore_errors=True)
        command = ["clone", "--filter=blob:none", "--no-tags"]
        if ref:
            command += ["--branch", ref]
        command += [url, str(destination)]
        try:
            run_git(command, timeout=180)
            return
        except SyncError as exc:
            last_error = exc
            if attempt < attempts:
                delay = min(8.0, 0.5 * (2 ** (attempt - 1))) + random.uniform(0, 0.25)
                LOG.warning("clone_retry", extra={"attempt": attempt, "delay_seconds": round(delay, 2)})
                time.sleep(delay)
    raise last_error or SyncError("clone failed")


def sync(root: Path, refs: dict[str, str | None]) -> dict[str, object]:
    vendor = root / ".vendor"
    vendor.mkdir(parents=True, exist_ok=True)
    resolved: dict[str, object] = {"schema_version": 1, "sources": {}}
    for name, url in SOURCES.items():
        validate_source(name, url)
        target = vendor / name
        with tempfile.TemporaryDirectory(prefix=f"{name}-", dir=vendor) as temp:
            checkout = Path(temp) / "checkout"
            LOG.info("sync_started", extra={"source": name, "url": url})
            clone_with_retry(url, checkout, refs.get(name))
            commit = run_git(["rev-parse", "HEAD"], cwd=checkout)
            if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit.lower()):
                raise SyncError(f"Source {name} returned an invalid commit identifier")
            remote = run_git(["remote", "get-url", "origin"], cwd=checkout)
            validate_source(name, remote)
            backup = vendor / f".{name}.previous"
            shutil.rmtree(backup, ignore_errors=True)
            if target.exists():
                target.replace(backup)
            checkout.replace(target)
            shutil.rmtree(backup, ignore_errors=True)
            resolved["sources"][name] = {"url": url, "commit": commit}
            LOG.info("sync_completed", extra={"source": name, "commit": commit})
    manifest = root / "vendor-manifest.json"
    temporary = manifest.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(resolved, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(manifest)
    return resolved


def repository_root(script: Path) -> Path:
    root = script.resolve().parents[5]
    if not (root / "hub").is_dir() or not (root / ".git").exists():
        raise SyncError(f"Expected Connector Hub repository at {root}")
    return root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forgekit-ref", help="Branch, tag, or commit to check out")
    parser.add_argument("--hikmah-ref", help="Branch, tag, or commit to check out")
    parser.add_argument("--root", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format='{"level":"%(levelname)s","event":"%(message)s"}')
    try:
        root = args.root.resolve() if args.root else repository_root(Path(__file__))
        result = sync(root, {"forgekit": args.forgekit_ref, "hikmah-stack": args.hikmah_ref})
    except SyncError as exc:
        LOG.error("sync_failed: %s", exc)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
