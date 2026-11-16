# 校园活动票务与报名系统

本项目是软件工程实验三的实现部分，依据实验二的 UML 设计完成。程序使用 Python、Tkinter 和 SQLite，面向桌面环境运行。

## 目录

- `src/campus_ticketing/domain`：领域对象、枚举和状态机。
- `src/campus_ticketing/repositories`：SQLite 数据访问。
- `src/campus_ticketing/services`：活动、报名、签到、通知和审计业务。
- `src/campus_ticketing/scheduler`：候补递补和缺席处理。
- `src/campus_ticketing/ui`：桌面界面。
- `tests`：单元测试和集成测试。

## 运行

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m campus_ticketing.main
```

首次启动会在当前目录创建 SQLite 数据库，并插入演示数据。测试使用：

```powershell
python -m unittest discover -s tests -v
```

构建使用：

```powershell
python -m build
```

Windows 桌面检查可以直接双击 `run_gui.pyw` 启动。

## 默认演示账号

程序提供参与者、组织者、检票人员和管理员四类演示身份。正式使用时应在用户管理模块中替换演示数据。
