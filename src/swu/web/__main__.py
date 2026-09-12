"""
Run the backend:

    python -m swu.web                 # 127.0.0.1:8000 (local only, default)
    python -m swu.web --host 0.0.0.0  # bind for LAN play (later phase)
    python -m swu.web --export-openapi docs/openapi.json   # write schema and exit

Binding defaults to localhost; LAN hosting is a flag change, not a rewrite.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="SWU web UI backend")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Bind host (default 127.0.0.1; use 0.0.0.0 for LAN)")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="Auto-reload (dev)")
    parser.add_argument("--export-openapi", metavar="PATH",
                        help="Write the OpenAPI schema to PATH and exit")
    args = parser.parse_args()

    from swu.web.app import app

    if args.export_openapi:
        out = Path(args.export_openapi)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
        print(f"Wrote OpenAPI schema to {out}")
        return

    import uvicorn
    uvicorn.run("swu.web.app:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
