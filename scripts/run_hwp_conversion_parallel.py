"""HWP→PDF PowerShell 변환기를 독립 shard 프로세스로 실행·모니터링한다."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs" / "hwp_conversion"
STATE = LOG_DIR / "processes.json"


def start(shards: int) -> int:
    """숨김 변환 프로세스를 시작하고 PID를 기록한다."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    for path in (ROOT / "metadata").glob(f"hwp_pdf_manifest.shard-*-of-{shards}.jsonl"): path.unlink()
    processes = []
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    for index in range(shards):
        output = (LOG_DIR / f"shard-{index}.out.log").open("w", encoding="utf-8")
        error = (LOG_DIR / f"shard-{index}.err.log").open("w", encoding="utf-8")
        command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts/convert_hwp_to_pdf.ps1"), "-ShardIndex", str(index), "-ShardCount", str(shards)]
        process = subprocess.Popen(command, cwd=ROOT, stdout=output, stderr=error, creationflags=flags)
        processes.append({"shard": index, "pid": process.pid, "stdout": str(output.name), "stderr": str(error.name)})
        output.close(); error.close()
    STATE.write_text(json.dumps({"started_at": datetime.now(timezone.utc).isoformat(), "shards": shards, "processes": processes}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"started": len(processes), "pids": [p["pid"] for p in processes]}, ensure_ascii=False)); return 0


def run_foreground(shards: int) -> int:
    """실행 셀을 유지하며 shard를 병렬 처리하고 30초마다 진행률을 출력한다."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    for path in (ROOT / "metadata").glob(f"hwp_pdf_manifest.shard-*-of-{shards}.jsonl"): path.unlink()
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    running = []
    for index in range(shards):
        output = (LOG_DIR / f"shard-{index}.out.log").open("w", encoding="utf-8")
        error = (LOG_DIR / f"shard-{index}.err.log").open("w", encoding="utf-8")
        command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts/convert_hwp_to_pdf.ps1"), "-ShardIndex", str(index), "-ShardCount", str(shards)]
        process = subprocess.Popen(command, cwd=ROOT, stdout=output, stderr=error, creationflags=flags)
        running.append((index, process, output, error))
    STATE.write_text(json.dumps({"started_at": datetime.now(timezone.utc).isoformat(), "shards": shards, "processes": [{"shard": i, "pid": p.pid, "stdout": o.name, "stderr": e.name} for i,p,o,e in running]}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"started": shards, "pids": [p.pid for _,p,_,_ in running]}, ensure_ascii=False), flush=True)
    while any(process.poll() is None for _, process, _, _ in running):
        time.sleep(30)
        pdf_count = len(list((ROOT / "corpus/pdf").rglob("*.pdf")))
        print(json.dumps({"pdf_count": pdf_count, "shards": [{"shard": i, "running": p.poll() is None, "returncode": p.poll()} for i,p,_,_ in running]}, ensure_ascii=False), flush=True)
    codes = []
    for index, process, output, error in running:
        codes.append(process.returncode); output.close(); error.close()
    print(json.dumps({"completed": shards, "returncodes": codes, "pdf_count": len(list((ROOT / "corpus/pdf").rglob("*.pdf")))}, ensure_ascii=False), flush=True)
    return 1 if any(code != 0 for code in codes) else 0


def status() -> int:
    """기록된 PID와 로그 마지막 줄로 진행 상태를 출력한다."""
    if not STATE.exists(): raise FileNotFoundError("실행 상태 파일이 없습니다.")
    state = json.loads(STATE.read_text(encoding="utf-8-sig")); rows = []
    for item in state["processes"]:
        try:
            os.kill(item["pid"], 0); running = True
        except OSError: running = False
        output = Path(item["stdout"]); error = Path(item["stderr"])
        out_lines = output.read_text(encoding="utf-8", errors="replace").splitlines() if output.exists() else []
        err_lines = error.read_text(encoding="utf-8", errors="replace").splitlines() if error.exists() else []
        rows.append({"shard": item["shard"], "pid": item["pid"], "running": running, "last_output": out_lines[-1] if out_lines else None, "last_error": err_lines[-1] if err_lines else None})
    manifests = len(list((ROOT / "metadata").glob("hwp_pdf_manifest.shard-*.jsonl")))
    print(json.dumps({"processes": rows, "completed_manifests": manifests}, ensure_ascii=False)); return 0


def main() -> int:
    parser = argparse.ArgumentParser(); sub = parser.add_subparsers(dest="command", required=True)
    launch = sub.add_parser("start"); launch.add_argument("--shards", type=int, default=4)
    run_parser = sub.add_parser("run"); run_parser.add_argument("--shards", type=int, default=4)
    sub.add_parser("status"); args = parser.parse_args()
    if args.command == "start": return start(args.shards)
    if args.command == "run": return run_foreground(args.shards)
    return status()


if __name__ == "__main__": raise SystemExit(main())
