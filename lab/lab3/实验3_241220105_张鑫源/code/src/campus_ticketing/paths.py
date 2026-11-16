"""项目路径和运行时配置。"""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = DATA_DIR / "campus_ticketing.sqlite3"
EXPORT_DIR = DATA_DIR / "exports"


def ensure_runtime_directories() -> None:
    """创建运行时需要的目录。"""

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
