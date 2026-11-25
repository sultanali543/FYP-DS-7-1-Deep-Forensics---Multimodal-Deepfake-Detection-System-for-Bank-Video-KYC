"""Start the connected app on this computer only."""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
import webbrowser

import uvicorn

from .app import create_app, model_readiness
from .config import Settings


def open_browser_window(url):
    """Open a visible browser window on Windows after the server is ready."""
    if os.name == "nt":
        folders = [os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)")]
        for relative in ("Google/Chrome/Application/chrome.exe", "Microsoft/Edge/Application/msedge.exe"):
            for folder in folders:
                if not folder:
                    continue
                browser = Path(folder) / relative
                if browser.is_file():
                    try:
                        subprocess.Popen([str(browser), "--new-window", url],
                                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                        return True
                    except OSError:
                        continue
    try:
        return webbrowser.open(url, new=1, autoraise=True)
    except OSError:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        settings = Settings()
    except ValueError as error:
        print(str(error))
        return 1
    model = model_readiness(settings)
    if not model["ready"]:
        print(model["reason"])
        return 1
    if args.check:
        print(f"Trained model ready: {model['model_version']}")
        print(f"Audio model: {model.get('audio_model_version', 'not installed')}")
        return 0
    if not (settings.frontend / "index.html").is_file():
        print("The connected frontend has not been built. Run npm run build:live from frontend, then start the backend again.")
        return 1
    # Reserve the exact loopback port before opening a browser.
    listener = socket.socket()
    try:
        listener.bind(("127.0.0.1", 8000))
        listener.listen(128)
    except OSError:
        listener.close()
        print("Port 8000 is already in use. Close the previous app window or stop its server, then retry.")
        return 1
    server = uvicorn.Server(uvicorn.Config(create_app(settings), host="127.0.0.1", port=8000,
                                         workers=1, limit_concurrency=16, log_level="info"))

    def open_when_ready():
        for _ in range(150):
            if server.started:
                url = "http://127.0.0.1:8000"
                if not open_browser_window(url):
                    print(f"Open {url} in your browser.", flush=True)
                return
            if server.should_exit:
                return
            time.sleep(0.2)

    if not args.no_browser:
        threading.Thread(target=open_when_ready, daemon=True).start()
    print("Deep Forensics: http://127.0.0.1:8000")
    print("Keep this window open. Press Ctrl+C to stop; an active video may finish first.")
    try:
        server.run(sockets=[listener])
    finally:
        listener.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
