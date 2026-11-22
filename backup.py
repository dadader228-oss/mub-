#!/usr/bin/env python3
"""Simple SQLite backup utility."""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

SRC = Path("storage/bot_store.db")
DST_DIR = Path("storage/backups")


def main() -> None:
    if not SRC.exists():
        print("Database not found:", SRC)
        return
    DST_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = DST_DIR / f"bot_store_{stamp}.db"
    shutil.copy2(SRC, dst)
    print("Backup created:", dst)


if __name__ == "__main__":
    main()
