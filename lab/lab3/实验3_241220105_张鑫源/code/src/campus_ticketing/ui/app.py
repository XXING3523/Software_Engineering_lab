"""校园活动票务系统桌面界面。"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from campus_ticketing.application import Application
from campus_ticketing.domain.enums import Role
from campus_ticketing.domain.exceptions import DomainError


class MainWindow:
    """提供面向四类角色的桌面操作窗口。"""

    def __init__(self, application: Application) -> None:
        self.application = application
        self.root = tk.Tk()
        self.root.title("校园活动票务与报名系统")
        self.root.geometry("1100x720")
        self.root.minsize(900, 600)
        self.current_user = application.users[0]
        self.keyword_var = tk.StringVar()
        self.activity_title = tk.StringVar()
        self.activity_location = tk.StringVar()
        self.activity_description = tk.StringVar()
        self.ticket_code_var = tk.StringVar()
        self.admin_text: tk.Text | None = None
        self.activity_tree: ttk.Treeview | None = None
        self.registration_tree: ttk.Treeview | None = None
        self.status_var = tk.StringVar(value="系统已启动")
        self._build_layout()
        self._refresh_all()

    def run(self) -> None:
        """启动事件循环。"""

        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.mainloop()

    def _build_layout(self) -> None:
        header = ttk.Frame(self.root, padding=12)
        header.pack(fill=tk.X)
        ttk.Label(
            header,
            text="校园活动票务与报名系统",
            font=("Microsoft YaHei UI", 18, "bold"),
        ).pack(side=tk.LEFT)
        ttk.Label(header, text="当前演示身份：").pack(side=tk.LEFT, padx=(36, 4))
        self.role_box = ttk.Combobox(header, state="readonly", width=18)
        self.role_box["values"] = [
            "参与者 participant",
            "组织者 organizer",
            "检票人员 checker",
            "管理员 admin",
        ]
        self.role_box.current(0)
        self.role_box.bind("<<ComboboxSelected>>", self._switch_role)
        self.role_box.pack(side=tk.LEFT)
        ttk.Button(header, text="刷新", command=self._refresh_all).pack(
            side=tk.RIGHT, padx=4
        )

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))
        self.browse_tab = ttk.Frame(notebook, padding=10)
        self.registration_tab = ttk.Frame(notebook, padding=10)
        self.management_tab = ttk.Frame(notebook, padding=10)
        self.checkin_tab = ttk.Frame(notebook, padding=10)
        self.admin_tab = ttk.Frame(notebook, padding=10)
        notebook.add(self.browse_tab, text="活动广场")
        notebook.add(self.registration_tab, text="我的报名")
        notebook.add(self.management_tab, text="活动管理")
        notebook.add(self.checkin_tab, text="扫码签到")
        notebook.add(self.admin_tab, text="管理员中心")
        self._build_browse_tab()
        self._build_registration_tab()
        self._build_management_tab()
        self._build_checkin_tab()
        self._build_admin_tab()
        ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN).pack(
            fill=tk.X, side=tk.BOTTOM
        )

    def _build_browse_tab(self) -> None:
        search = ttk.Frame(self.browse_tab)
        search.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(search, text="关键词").pack(side=tk.LEFT)
        ttk.Entry(search, textvariable=self.keyword_var, width=30).pack(
            side=tk.LEFT, padx=6
        )
        ttk.Button(search, text="查询", command=self._refresh_activities).pack(side=tk.LEFT)
        columns = ("id", "title", "location", "status")
        self.activity_tree = ttk.Treeview(
            self.browse_tab, columns=columns, show="headings", height=18
        )
        headings = {"id": "编号", "title": "活动标题", "location": "地点", "status": "状态"}
        for column in columns:
            self.activity_tree.heading(column, text=headings[column])
            self.activity_tree.column(column, width=120 if column != "title" else 420)
        self.activity_tree.pack(fill=tk.BOTH, expand=True)
        actions = ttk.Frame(self.browse_tab)
        actions.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(actions, text="查看详情", command=self._show_activity).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(actions, text="报名/候补", command=self._register_selected).pack(
            side=tk.LEFT, padx=4
        )

    def _build_registration_tab(self) -> None:
        columns = ("id", "activity", "status", "ticket")
        self.registration_tree = ttk.Treeview(
            self.registration_tab, columns=columns, show="headings", height=18
        )
        headings = {"id": "报名编号", "activity": "活动编号", "status": "状态", "ticket": "票码"}
        for column in columns:
            self.registration_tree.heading(column, text=headings[column])
            self.registration_tree.column(column, width=180)
        self.registration_tree.pack(fill=tk.BOTH, expand=True)
        ttk.Button(
            self.registration_tab, text="取消选中报名", command=self._cancel_selected
        ).pack(anchor=tk.W, pady=(8, 0))

    def _build_management_tab(self) -> None:
        form = ttk.LabelFrame(self.management_tab, text="创建活动", padding=10)
        form.pack(fill=tk.X, anchor=tk.N)
        for row, label, variable in [
            (0, "标题", self.activity_title),
            (1, "地点", self.activity_location),
            (2, "简介", self.activity_description),
        ]:
            ttk.Label(form, text=label, width=8).grid(row=row, column=0, sticky=tk.W, pady=4)
            ttk.Entry(form, textvariable=variable, width=70).grid(
                row=row, column=1, sticky=tk.EW, pady=4
            )
        ttk.Button(form, text="创建并进入草稿", command=self._create_activity).grid(
            row=3, column=1, sticky=tk.W, pady=8
        )
        form.columnconfigure(1, weight=1)
        ttk.Label(
            self.management_tab,
            text="当前版本将场次和票种维护交由服务层完成，管理员中心可查看审核结果。",
            foreground="#555555",
        ).pack(anchor=tk.W, pady=12)

    def _build_checkin_tab(self) -> None:
        form = ttk.LabelFrame(self.checkin_tab, text="检票签到", padding=14)
        form.pack(anchor=tk.NW, fill=tk.X)
        ttk.Label(form, text="票码", width=10).grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(form, textvariable=self.ticket_code_var, width=40).grid(
            row=0, column=1, sticky=tk.W, pady=5
        )
        ttk.Button(form, text="确认签到", command=self._check_in).grid(
            row=1, column=1, sticky=tk.W, pady=8
        )

    def _build_admin_tab(self) -> None:
        actions = ttk.Frame(self.admin_tab)
        actions.pack(fill=tk.X, anchor=tk.NW)
        ttk.Button(actions, text="查看统计", command=self._show_statistics).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(actions, text="导出活动", command=self._export_activities).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(actions, text="运行缺席处理", command=self._mark_absent).pack(
            side=tk.LEFT, padx=4
        )
        self.admin_text = tk.Text(self.admin_tab, height=22, state=tk.DISABLED)
        self.admin_text.pack(fill=tk.BOTH, expand=True, pady=(12, 0))

    def _switch_role(self, _event: object = None) -> None:
        index = self.role_box.current()
        self.current_user = self.application.users[index]
        self.status_var.set(f"已切换为：{self.current_user.name}")
        self._refresh_all()

    def _refresh_all(self) -> None:
        self._refresh_activities()
        self._refresh_registrations()

    def _refresh_activities(self) -> None:
        if self.activity_tree is None:
            return
        for item in self.activity_tree.get_children():
            self.activity_tree.delete(item)
        activities = self.application.activities.list_published(self.keyword_var.get())
        for activity in activities:
            self.activity_tree.insert(
                "", tk.END, iid=str(activity.id), values=(
                    activity.id, activity.title, activity.location, activity.status.value
                )
            )

    def _refresh_registrations(self) -> None:
        if self.registration_tree is None:
            return
        for item in self.registration_tree.get_children():
            self.registration_tree.delete(item)
        if not self.current_user.has_role(Role.PARTICIPANT):
            return
        for registration in self.application.registrations.list_for_user(self.current_user):
            self.registration_tree.insert(
                "", tk.END, iid=str(registration.id), values=(
                    registration.id,
                    registration.activity_id,
                    registration.status.value,
                    registration.ticket_code or "候补中",
                )
            )

    def _selected_activity_id(self) -> int | None:
        if self.activity_tree is None:
            return None
        selected = self.activity_tree.selection()
        return int(selected[0]) if selected else None

    def _selected_registration_id(self) -> int | None:
        if self.registration_tree is None:
            return None
        selected = self.registration_tree.selection()
        return int(selected[0]) if selected else None

    def _show_activity(self) -> None:
        activity_id = self._selected_activity_id()
        if activity_id is None:
            self._warn("请先选择一个活动")
            return
        details = self.application.activities.details(activity_id)
        activity = details["activity"]
        lines = [f"{activity.title}", f"地点：{activity.location}", activity.description]
        for item in details["sessions"]:
            session = item["session"]
            lines.append(
                f"场次 {session.id}：{session.start_at}，"
                f"剩余 {session.remaining_capacity}/{session.capacity}"
            )
            for ticket in item["tickets"]:
                lines.append(f"  - {ticket.name}：剩余 {ticket.remaining_capacity}/{ticket.capacity}")
        messagebox.showinfo("活动详情", "\n".join(lines))

    def _register_selected(self) -> None:
        activity_id = self._selected_activity_id()
        if activity_id is None:
            self._warn("请先选择一个活动")
            return
        try:
            details = self.application.activities.details(activity_id)
            session = details["sessions"][0]["session"]
            ticket = details["sessions"][0]["tickets"][0]
            request_id = f"ui-{self.current_user.id}-{activity_id}"
            result = self.application.registrations.register(
                self.current_user, activity_id, session.id, ticket.id, request_id
            )
            self.status_var.set(result.message)
            self._refresh_all()
            messagebox.showinfo("报名结果", result.message)
        except DomainError as error:
            self._warn(str(error))

    def _cancel_selected(self) -> None:
        registration_id = self._selected_registration_id()
        if registration_id is None:
            self._warn("请先选择一条报名记录")
            return
        try:
            result = self.application.registrations.cancel(self.current_user, registration_id)
            self.status_var.set(result.message)
            self._refresh_all()
        except DomainError as error:
            self._warn(str(error))

    def _create_activity(self) -> None:
        try:
            activity = self.application.activities.create_activity(
                self.current_user,
                self.activity_title.get(),
                self.activity_description.get(),
                self.activity_location.get(),
            )
            self.status_var.set(f"已创建草稿活动 {activity.id}")
            self.activity_title.set("")
            self.activity_location.set("")
            self.activity_description.set("")
        except DomainError as error:
            self._warn(str(error))

    def _check_in(self) -> None:
        try:
            check_in = self.application.checkins.check_in(
                self.current_user, self.ticket_code_var.get()
            )
            self.status_var.set(f"签到成功，记录编号 {check_in.id}")
        except DomainError as error:
            self._warn(str(error))

    def _show_statistics(self) -> None:
        try:
            statistics = self.application.reporting.statistics(self.current_user)
            text = "\n".join(f"{key}: {value}" for key, value in statistics.items())
            self._write_admin_text(text)
        except DomainError as error:
            self._warn(str(error))

    def _export_activities(self) -> None:
        try:
            target = filedialog.asksaveasfilename(
                title="导出活动清单",
                defaultextension=".csv",
                filetypes=[("CSV 文件", "*.csv")],
            )
            if not target:
                return
            output = self.application.activities.export_activities(Path(target))
            self.status_var.set(f"活动已导出到 {output}")
        except (DomainError, OSError) as error:
            self._warn(str(error))

    def _mark_absent(self) -> None:
        try:
            changed = self.application.scheduler.mark_absent(self.current_user)
            self.status_var.set(f"本次处理了 {changed} 条缺席记录")
        except DomainError as error:
            self._warn(str(error))

    def _write_admin_text(self, text: str) -> None:
        self.admin_text.configure(state=tk.NORMAL)
        self.admin_text.delete("1.0", tk.END)
        self.admin_text.insert(tk.END, text)
        self.admin_text.configure(state=tk.DISABLED)

    def _warn(self, message: str) -> None:
        self.status_var.set(message)
        messagebox.showwarning("操作提示", message)

    def _close(self) -> None:
        self.application.close()
        self.root.destroy()
