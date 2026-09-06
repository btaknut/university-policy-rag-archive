from __future__ import annotations

from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from install_unhwp import safe_destination, select_asset


def test_select_asset_normalizes_common_platform_names():
    assert select_asset("Linux", "AMD64").filename.startswith("unhwp-linux-x86_64")
    assert select_asset("Darwin", "arm64").filename.startswith("unhwp-macos-aarch64")
    assert select_asset("Windows", "x86_64").filename.endswith(".zip")


def test_select_asset_rejects_unsupported_platform():
    with pytest.raises(RuntimeError, match="지원하지 않는 플랫폼"):
        select_asset("Linux", "aarch64")


def test_safe_destination_rejects_path_traversal(tmp_path: Path):
    with pytest.raises(RuntimeError, match="경로 이탈"):
        safe_destination(tmp_path, "../escape")
