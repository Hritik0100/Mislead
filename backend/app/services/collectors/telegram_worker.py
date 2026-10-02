"""Subprocess worker: runs a Telegram collection in isolation.

Why a subprocess: Telethon is asyncio-native and writes a sqlite session file.
Running it inside an ASGI worker would fight the server's event loop and risk
two writers on the same session. A dedicated process guarantees a clean
interpreter with no running loop.

Task JSON on stdin, result JSON on stdout. One JSON object per line on stdout;
the LAST line is the result. Progress goes to stderr so it can never corrupt
the result line.
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))


def main():
    try:
        task = json.loads(sys.stdin.read() or "{}")
    except Exception:
        task = {}
    from app.services.collectors.telegram import (
        TelegramCollector, TelethonDriver, TelegramConfig, redact_tg, ERROR,
    )

    out = {"status": ERROR, "reason_code": "init", "records": [], "errors": [],
           "session_reused": False}
    cfg = TelegramConfig.from_env(task.get("session") or "telegram")
    sdir = task.get("session_dir") or None
    try:
        driver = TelethonDriver(cfg, sdir)
        col = TelegramCollector(session_dir=sdir, driver=driver)
        res = asyncio.run(col.collect_async(task))
        out.update(res)
    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        out.update(status=ERROR, reason_code="worker_failed",
                   errors=[f"{type(e).__name__}: {str(e)[:180]}" if str(e)
                           else type(e).__name__])
        out = redact_tg(out, cfg.secret_values())
    try:
        print(json.dumps(out), flush=True)
    except Exception:
        print(json.dumps({"status": ERROR, "reason_code": "unserializable_result",
                          "records": [], "errors": ["result could not be serialised"]}),
              flush=True)


if __name__ == "__main__":
    main()
