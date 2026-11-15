from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_env() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip("\"'"))


def main() -> int:
    load_env()
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        print("Node.js/npm is required. Install Node LTS and retry.")
        return 2
    if not (ROOT / "frontend" / "node_modules" / "vite").exists():
        print("Frontend dependencies are missing. Run: npm install --prefix frontend")
        return 2

    commands = [
        [
            sys.executable, "-m", "uvicorn", "backend.app.main:app",
            "--host", "127.0.0.1", "--port", "8000",
        ],
        [npm, "--prefix", str(ROOT / "frontend"), "run", "dev"],
    ]
    processes: list[subprocess.Popen[bytes]] = []
    try:
        for command in commands:
            processes.append(subprocess.Popen(command, cwd=ROOT))
        print("Hatch API: http://127.0.0.1:8000")
        print("Hatch UI:  http://127.0.0.1:5173")
        print("Press Ctrl+C to stop both services.")
        while all(process.poll() is None for process in processes):
            time.sleep(0.5)
        return next((process.returncode or 0 for process in processes if process.poll() is not None), 0)
    except KeyboardInterrupt:
        return 0
    finally:
        for process in processes:
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
