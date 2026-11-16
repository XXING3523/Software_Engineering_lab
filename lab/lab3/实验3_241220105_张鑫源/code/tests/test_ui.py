"""Tkinter 界面冒烟测试。"""

import tempfile
import tkinter as tk
import unittest
from pathlib import Path

from campus_ticketing.application import Application
from campus_ticketing.ui import MainWindow


class UserInterfaceSmokeTests(unittest.TestCase):
    """验证主窗口和主要标签页可以创建。"""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.application = Application(str(Path(self.temp_dir.name) / "ui.sqlite3"))
        self.root = tk.Tk()
        self.root.withdraw()
        try:
            self.window = MainWindow(self.application)
        except Exception:
            self.root.destroy()
            self.application.close()
            self.temp_dir.cleanup()
            raise
        self.root.update_idletasks()

    def tearDown(self) -> None:
        self.application.close()
        self.root.destroy()
        self.temp_dir.cleanup()

    def test_main_window_contains_expected_tabs_and_activity(self) -> None:
        self.assertIsNotNone(self.window.notebook)
        self.assertEqual(len(self.window.notebook.tabs()), 5)
        self.assertIsNotNone(self.window.activity_tree)
        self.assertEqual(len(self.window.activity_tree.get_children()), 1)
        self.assertEqual(self.window.role_box.get(), "参与者 participant")


if __name__ == "__main__":
    unittest.main()
