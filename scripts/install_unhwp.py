"""검증된 unhwp 실행 파일을 저장소 로컬 도구 디렉터리에 설치한다."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import NamedTuple
from urllib.request import Request, urlopen
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.9.1"
RELEASE_BASE = f"https://github.com/iyulab/unhwp/releases/download/v{VERSION}"


class Asset(NamedTuple):
    filename: str
    sha256: str


ASSETS = {
    ("linux", "x86_64"): Asset(
        f"unhwp-linux-x86_64-v{VERSION}.tar.gz",
        "f71a07a448e69219c5de380d3a300d515aece3eabccfc879a6765dbd3b0da409",
    ),
    ("darwin", "x86_64"): Asset(
        f"unhwp-macos-x86_64-v{VERSION}.tar.gz",
        "9dd178a920a81c85eb1f5bab3362d61731a862de30a2468f4ca3fc5a5add4140",
    ),
    ("darwin", "aarch64"): Asset(
        f"unhwp-macos-aarch64-v{VERSION}.tar.gz",
        "dfd9acd545b6d53d78b6758ca0940887c569878ce95abc69ce9f3717bde09533",
    ),
    ("windows", "x86_64"): Asset(
        f"unhwp-windows-x86_64-v{VERSION}.zip",
        "3e83c2bed14984c54dd980121bb40f59720b8c2f34cd88ff67ef30450597f975",
    ),
}


def normalize_platform(system: str, machine: str) -> tuple[str, str]:
    normalized_system = system.lower()
    normalized_machine = machine.lower()
    if normalized_machine in {"amd64", "x64"}:
        normalized_machine = "x86_64"
    elif normalized_machine == "arm64":
        normalized_machine = "aarch64"
    return normalized_system, normalized_machine


def select_asset(system: str, machine: str) -> Asset:
    key = normalize_platform(system, machine)
    if key not in ASSETS:
        raise RuntimeError(
            f"지원하지 않는 플랫폼: {system}/{machine}. "
            "지원 대상은 Linux x86_64, macOS x86_64/aarch64, Windows x86_64입니다."
        )
    return ASSETS[key]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_destination(root: Path, member_name: str) -> Path:
    destination = (root / member_name).resolve()
    if not destination.is_relative_to(root.resolve()):
        raise RuntimeError(f"압축 파일 경로 이탈 감지: {member_name}")
    return destination


def extract_archive(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as bundle:
            for info in bundle.infolist():
                safe_destination(destination, info.filename)
            bundle.extractall(destination)
        return
    with tarfile.open(archive, "r:gz") as bundle:
        for member in bundle.getmembers():
            safe_destination(destination, member.name)
            if member.issym() or member.islnk():
                raise RuntimeError(f"압축 파일 링크 항목 거부: {member.name}")
            if not (member.isfile() or member.isdir()):
                raise RuntimeError(f"압축 파일 특수 항목 거부: {member.name}")
        if sys.version_info >= (3, 12):
            bundle.extractall(destination, filter="data")
        else:
            bundle.extractall(destination)


def version_output(binary: Path) -> str:
    result = subprocess.run(
        [str(binary), "version"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return (result.stdout + "\n" + result.stderr).strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target",
        type=Path,
        default=ROOT / ".tools/unhwp" / f"v{VERSION}",
    )
    parser.add_argument("--print-path", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target = args.target.resolve()
    executable_name = "unhwp.exe" if os.name == "nt" else "unhwp"
    installed = target / executable_name
    if installed.is_file() and not args.force:
        output = version_output(installed)
        if f"unhwp {VERSION}" not in output:
            raise RuntimeError(f"기존 unhwp 버전 불일치: {output[:200]}")
        print(installed if args.print_path else f"already installed: {installed}")
        return 0

    asset = select_asset(platform.system(), platform.machine())
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="install-unhwp-", dir=target.parent) as temporary:
        temp_dir = Path(temporary)
        archive = temp_dir / asset.filename
        request = Request(
            f"{RELEASE_BASE}/{asset.filename}",
            headers={"User-Agent": "university-policy-rag-archive/portable-gate"},
        )
        with urlopen(request, timeout=120) as response, archive.open("wb") as stream:
            shutil.copyfileobj(response, stream)
        actual = sha256_file(archive)
        if actual != asset.sha256:
            raise RuntimeError(f"unhwp 배포본 SHA-256 불일치: {actual}")
        extracted = temp_dir / "extracted"
        extract_archive(archive, extracted)
        candidates = sorted(extracted.rglob(executable_name))
        if len(candidates) != 1:
            raise RuntimeError(f"unhwp 실행 파일 수가 예상과 다름: {len(candidates)}")
        staged = temp_dir / "staged"
        staged.mkdir()
        shutil.copy2(candidates[0], staged / executable_name)
        if os.name != "nt":
            (staged / executable_name).chmod(0o755)
        output = version_output(staged / executable_name)
        if f"unhwp {VERSION}" not in output:
            raise RuntimeError(f"설치본 unhwp 버전 불일치: {output[:200]}")
        if target.exists():
            if not args.force:
                raise RuntimeError(f"설치 대상이 이미 존재함: {target}")
            shutil.rmtree(target)
        staged.replace(target)

    print(installed if args.print_path else f"installed: {installed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
