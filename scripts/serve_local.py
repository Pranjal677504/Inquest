"""Start the opt-in local investigation server, with one worker and no reloader."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from werkzeug.serving import make_server  # noqa: E402
from local_app import create_local_app  # noqa: E402
from local_jobs import JobManager  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "runs" / "local-web")
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("Choose a port from 1024 to 65535")
    manager = JobManager(args.data_dir, ROOT / "datasets")
    try:
        origin = f"http://127.0.0.1:{args.port}"
        application = create_local_app(manager, origin)
        server = make_server("127.0.0.1", args.port, application, threaded=True)
        print(f"Local offline investigations: {origin}/investigate", flush=True)
        print(f"Saved jobs: {manager.root}\nNo model calls. Press Ctrl+C to stop.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    finally:
        manager.close()


if __name__ == "__main__":
    main()
