"""程序入口。"""

from campus_ticketing.application import Application
from campus_ticketing.ui import MainWindow


def main() -> None:
    """创建应用并启动桌面窗口。"""

    application = Application()
    window = MainWindow(application)
    window.run()


if __name__ == "__main__":
    main()
