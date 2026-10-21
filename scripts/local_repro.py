"""Run native Linux services against the configured database."""
from pathlib import Path
import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / ".run"
STATE = RUN / "services.json"


def owned_process(service):
    result = subprocess.run(
        ["ps", "-p", str(service["pid"]), "-o", "command="],
        capture_output=True, text=True,
    )
    # Defunct Linux children no longer serve requests.
    status = subprocess.run(["ps", "-p", str(service["pid"]), "-o", "stat="], capture_output=True, text=True)
    return result.returncode == 0 and not status.stdout.strip().startswith("Z") and service["marker"] in result.stdout


def read_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def stop():
    for name, service in read_state().items():
        if owned_process(service):
            os.killpg(service["pid"], signal.SIGTERM)
            deadline = time.monotonic() + 10
            while owned_process(service) and time.monotonic() < deadline:
                time.sleep(0.1)
            if owned_process(service):
                raise SystemExit(f"{name} is still stopping; try stop again shortly.")
            print(f"Stopped {name}")
    STATE.unlink(missing_ok=True)


def start():
    state = read_state()
    if any(owned_process(service) for service in state.values()):
        raise SystemExit("Services already running; use status or stop first.")
    for port in (8000, 5173):
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                raise SystemExit(f"Port {port} is occupied; stop its service first.")
    python = ROOT / ".venv/bin/python"
    node = os.getenv("TALENTGRAPH_NODE") or shutil.which("node")
    if not node and (RUN / "node").is_file():
        node = str(RUN / "node")
    vite = ROOT / "apps/web/node_modules/vite/bin/vite.js"
    if not python.exists() or not node or not vite.exists():
        raise SystemExit("Create .venv with Python 3.12, install requirements.txt, and run npm ci in apps/web.")
    RUN.mkdir(exist_ok=True)
    from dotenv import dotenv_values

    env = {key: value for key, value in {**dotenv_values(ROOT / ".env"), **os.environ}.items() if value is not None}
    database = Path(env.get("TALENTGRAPH_DB_PATH") or "data/talentgraph.db").expanduser()
    if not database.is_absolute():
        database = ROOT / database
    database = database.resolve()
    if database.exists() and not database.is_file():
        raise SystemExit(f"Database path is not a file: {database}")
    database.parent.mkdir(parents=True, exist_ok=True)
    for key in ("TALENTGRAPH_DB", "COURSE_RAG_DB"):
        value = env.get(key)
        if value:
            path = Path(value).expanduser()
            if not path.is_absolute():
                path = ROOT / path
            if path.resolve() != database:
                raise SystemExit(f"{key} must refer to the same database: {database}")
    print(f"Using database: {database} (initialized on first launch if absent)", flush=True)
    env.update({
        "TALENTGRAPH_DB_PATH": str(database),
        "TALENTGRAPH_DB": str(database),
        "COURSE_RAG_DB": str(database),
        "PYTHONUNBUFFERED": "1",
    })
    commands = {
        "api": ([str(python), "-m", "uvicorn", "apps.api.main:app", "--host", "127.0.0.1", "--port", "8000"], ROOT, "apps.api.main:app"),
        "web": ([node, str(vite), "--host", "127.0.0.1", "--port", "5173", "--strictPort"], ROOT / "apps/web", str(vite)),
    }
    try:
        for name, (command, cwd, marker) in commands.items():
            with (RUN / f"{name}.log").open("a") as log:
                process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                           stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            state[name] = {"pid": process.pid, "marker": marker}
            STATE.write_text(json.dumps(state, indent=2))
        deadline = time.monotonic() + 90
        pending = {"api": "http://127.0.0.1:8000/api/health", "web": "http://127.0.0.1:5173"}
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        while pending and time.monotonic() < deadline:
            for name, url in list(pending.items()):
                if not owned_process(state[name]):
                    raise RuntimeError(f"{name} exited; see {RUN / (name + '.log')}")
                try:
                    with opener.open(url, timeout=2) as response:
                        if response.status == 200:
                            del pending[name]
                except OSError:
                    pass
            if pending:
                time.sleep(1)
        if pending:
            raise RuntimeError(f"Startup timed out: {list(pending)}; see .run logs")
    except BaseException:
        stop()
        raise
    print("讯飞智聘: http://localhost:5173")
    print("API docs: http://localhost:8000/docs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "stop", "status"], default="start", nargs="?")
    action = parser.parse_args().action
    if action == "start":
        start()
    elif action == "stop":
        stop()
    else:
        state = read_state()
        for name, service in state.items():
            print(f"{name}: {'running' if owned_process(service) else 'stopped'} (PID {service['pid']})")
        if not state:
            print("No services started by this launcher.")
