"""Windows 桌面启动入口。"""

from pathlib import Path
import sys


CODE_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(CODE_ROOT / "src"))

from campus_ticketing.main import main  # noqa: E402


if __name__ == "__main__":
    main()
