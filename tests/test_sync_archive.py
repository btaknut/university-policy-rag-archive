from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sync_archive


def commands_for(monkeypatch, rechunk: bool) -> list[list[str]]:
    commands: list[list[str]] = []
    monkeypatch.setattr(sync_archive, "parse_args", lambda: SimpleNamespace(rechunk=rechunk))
    monkeypatch.setattr(sync_archive.sys, "platform", "linux")
    monkeypatch.setattr(sync_archive.subprocess, "run", lambda command, **kwargs: commands.append(command))
    assert sync_archive.main() == 0
    return commands


def test_sync_defaults_to_incremental_chunks(monkeypatch):
    commands = commands_for(monkeypatch, False)
    chunk = next(command for command in commands if "build_chunks.py" in " ".join(command))
    assert chunk[-2:] == ["--mode", "incremental"]


def test_sync_rechunk_requires_explicit_flag(monkeypatch):
    commands = commands_for(monkeypatch, True)
    chunk = next(command for command in commands if "build_chunks.py" in " ".join(command))
    assert chunk[-3:] == ["--mode", "rechunk", "--allow-id-changes"]
