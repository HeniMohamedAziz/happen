from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

APP_NAME = "Happen"

STYLESHEET = """
QWidget {
    background: #f7f8fa;
    color: #202a35;
    font-family: 'Segoe UI';
    font-size: 10pt;
}
QMainWindow, QDialog {
    background: #f7f8fa;
}
QLabel#heading {
    font-size: 18pt;
    font-weight: 650;
    color: #182433;
}
QLabel#section {
    font-size: 9pt;
    font-weight: 700;
    color: #748091;
    letter-spacing: 1px;
}
QLabel#userName {
    font-size: 16pt;
    font-weight: 650;
}
QLabel#funds {
    font-weight: 600;
    color: #344254;
}
QLabel#muted {
    color: #788493;
}
QLabel#error {
    color: #b43f3a;
}
QPushButton {
    background: #ffffff;
    border: 1px solid #dce1e7;
    border-radius: 7px;
    padding: 8px 12px;
}
QPushButton:hover {
    background: #edf2f6;
}
QPushButton:disabled {
    color: #a0aab6;
    background: #f2f4f7;
}
QPushButton#quiet {
    border: 0;
    background: transparent;
    color: #49657b;
}
QListWidget, QTabWidget::pane, QTableWidget {
    background: #ffffff;
    border: 1px solid #e1e5eb;
    border-radius: 8px;
}
QListWidget {
    padding: 5px;
}
QListWidget::item {
    padding: 10px;
    border-radius: 5px;
}
QListWidget::item:selected {
    background: #eef0f3;
    color: #202a35;
}
QTabBar::tab {
    background: transparent;
    padding: 10px 14px;
    color: #657181;
}
QTabBar::tab:selected {
    color: #344254;
    border-bottom: 2px solid #8290a0;
    font-weight: 600;
}
QHeaderView::section {
    background: #f4f6f8;
    color: #778393;
    border: 0;
    padding: 9px;
    font-weight: 600;
}
QLineEdit, QDoubleSpinBox {
    background: transparent;
    border: 0;
    padding: 6px;
}
QCheckBox {
    background: transparent;
    spacing: 0px;
}
QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border: 2px solid #64748b;
    border-radius: 4px;
    background: #ffffff;
}
QCheckBox::indicator:hover {
    border-color: #347a51;
}
QCheckBox::indicator:checked {
    background: #347a51;
    border: 2px solid #347a51;
}
QWidget#divider {
    background: #e4e8ed;
}
"""


def database_path() -> Path:
    root = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root / "happen.db"


def asset_path(relative: str) -> Path:
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return bundle_root / relative


class Store:
    def __init__(self, path: Path):
        self.path = path
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE COLLATE NOCASE NOT NULL,
                password_hash BLOB NOT NULL,
                salt BLOB NOT NULL,
                display_name TEXT NOT NULL,
                total_funds REAL NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
                title TEXT NOT NULL,
                order_index INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS tabs (
                id INTEGER PRIMARY KEY,
                goal_id INTEGER NOT NULL REFERENCES goals ON DELETE CASCADE,
                title TEXT NOT NULL,
                order_index INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS steps (
                id INTEGER PRIMARY KEY,
                tab_id INTEGER NOT NULL REFERENCES tabs ON DELETE CASCADE,
                title TEXT NOT NULL,
                cost REAL NOT NULL DEFAULT 0,
                done INTEGER NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT '',
                deadline TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'Not Started',
                order_index INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        self.db.commit()

    def register(self, username: str, password: str, display: str) -> int:
        salt = os.urandom(16)
        hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
        with self.db:
            cur = self.db.execute(
                "INSERT INTO users(username, password_hash, salt, display_name) VALUES(?, ?, ?, ?)",
                (username.strip(), hashed, salt, display.strip()),
            )
            return int(cur.lastrowid)

    def authenticate(self, username: str, password: str):
        row = self.db.execute(
            "SELECT * FROM users WHERE username = ?",
            (username.strip(),),
        ).fetchone()
        if not row:
            return None
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), row["salt"], 310_000)
        if hmac.compare_digest(row["password_hash"], candidate):
            return row
        return None

    def goals(self, uid: int):
        return self.db.execute(
            "SELECT * FROM goals WHERE user_id = ? ORDER BY order_index, id",
            (uid,),
        ).fetchall()

    def tabs(self, gid: int):
        return self.db.execute(
            "SELECT * FROM tabs WHERE goal_id = ? ORDER BY order_index, id",
            (gid,),
        ).fetchall()

    def steps(self, tabid: int):
        return self.db.execute(
            "SELECT * FROM steps WHERE tab_id = ? ORDER BY order_index, id",
            (tabid,),
        ).fetchall()

    def totals(self, uid: int):
        return self.db.execute(
            """
            SELECT u.total_funds, COALESCE(SUM(s.cost), 0) AS spent
            FROM users u
            LEFT JOIN goals g ON g.user_id = u.id
            LEFT JOIN tabs t ON t.goal_id = g.id
            LEFT JOIN steps s ON s.tab_id = t.id AND s.done = 1
            WHERE u.id = ?
            GROUP BY u.id
            """,
            (uid,),
        ).fetchone()


class AuthDialog(QDialog):
    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self.user = None
        self.registering = False

        self.setWindowTitle(APP_NAME)
        self.setMinimumWidth(360)

        self.layout = QVBoxLayout(self)
        self.heading = QLabel("Welcome back")
        self.heading.setObjectName("heading")
        self.layout.addWidget(self.heading)

        self.form = QFormLayout()
        self.username = QLineEdit()
        self.username.setPlaceholderText("Username")

        self.password = QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)

        self.display = QLineEdit()
        self.display.setPlaceholderText("Display name")

        self.confirm = QLineEdit()
        self.confirm.setPlaceholderText("Confirm password")
        self.confirm.setEchoMode(QLineEdit.EchoMode.Password)

        self.form.addRow("Username", self.username)
        self.form.addRow("Password", self.password)
        self.layout.addLayout(self.form)

        self.error = QLabel()
        self.error.setObjectName("error")
        self.layout.addWidget(self.error)

        row = QHBoxLayout()
        self.submit = QPushButton("Log in")
        self.submit.clicked.connect(self.handle)

        self.toggle = QPushButton("Create account")
        self.toggle.setObjectName("quiet")
        self.toggle.clicked.connect(self.switch)

        row.addWidget(self.submit)
        row.addWidget(self.toggle)
        self.layout.addLayout(row)

    def switch(self):
        self.registering = not self.registering
        if self.registering:
            self.heading.setText("Create your account")
            self.submit.setText("Register")
            self.toggle.setText("Back to login")
            self.form.addRow("Display name", self.display)
            self.form.addRow("Confirm password", self.confirm)
        else:
            self.heading.setText("Welcome back")
            self.submit.setText("Log in")
            self.toggle.setText("Create account")
            self.form.removeRow(self.confirm)
            self.form.removeRow(self.display)
        self.error.clear()

    def handle(self):
        username = self.username.text().strip()
        password = self.password.text()
        if not username or not password:
            self.error.setText("Enter your username and password.")
            return

        try:
            if self.registering:
                if not self.display.text().strip():
                    raise ValueError("Enter a display name.")
                if len(password) < 8:
                    raise ValueError("Use a password with at least 8 characters.")
                if password != self.confirm.text():
                    raise ValueError("The passwords do not match.")
                uid = self.store.register(username, password, self.display.text())
                self.user = self.store.db.execute(
                    "SELECT * FROM users WHERE id = ?",
                    (uid,),
                ).fetchone()
            else:
                self.user = self.store.authenticate(username, password)
                if not self.user:
                    raise ValueError("Username or password is incorrect.")
            self.accept()
        except sqlite3.IntegrityError:
            self.error.setText("That username is already in use.")
        except ValueError as exc:
            self.error.setText(str(exc))


class MainWindow(QMainWindow):
    def __init__(self, store: Store, user):
        super().__init__()
        self.store = store
        self.uid = user["id"]

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(str(asset_path("assets/happen.ico"))))
        self.resize(1120, 740)

        root = QWidget()
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(16)

        top = QHBoxLayout()
        name = QLabel(user["display_name"])
        name.setObjectName("userName")
        top.addWidget(name)
        top.addStretch()

        self.funds_label = QLabel()
        self.funds_label.setObjectName("funds")
        top.addWidget(self.funds_label)

        self.funds_btn = QPushButton("Set funds")
        self.funds_btn.clicked.connect(self.set_funds)
        top.addWidget(self.funds_btn)

        settings = QToolButton()
        settings.setText("⚙")
        settings.setToolTip("Settings and backup")
        settings.setAutoRaise(True)

        menu = QMenu(self)
        backup = QAction("Backup now…", self)
        backup.triggered.connect(self.backup)
        menu.addAction(backup)

        logout = QAction("Log out", self)
        logout.triggered.connect(self.close)
        menu.addAction(logout)

        settings.clicked.connect(
            lambda: menu.exec(settings.mapToGlobal(settings.rect().bottomLeft()))
        )
        top.addWidget(settings)
        outer.addLayout(top)

        line = QWidget()
        line.setFixedHeight(1)
        line.setObjectName("divider")
        outer.addWidget(line)

        body = QHBoxLayout()
        body.setSpacing(20)
        outer.addLayout(body, 1)

        side = QVBoxLayout()
        side.setSpacing(10)
        body.addLayout(side, 1)

        hdr = QHBoxLayout()
        lbl = QLabel("YOUR GOALS")
        lbl.setObjectName("section")
        hdr.addWidget(lbl)
        hdr.addStretch()

        addgoal = QPushButton("+ Add")
        addgoal.clicked.connect(self.add_goal)
        hdr.addWidget(addgoal)
        side.addLayout(hdr)

        self.goal_list = QListWidget()
        self.goal_list.currentRowChanged.connect(self.select_goal)
        self.goal_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.goal_list.customContextMenuRequested.connect(self.goal_menu)
        side.addWidget(self.goal_list, 1)

        actions = QHBoxLayout()
        for text, callback in (("Rename", self.rename_goal), ("Delete", self.delete_goal)):
            btn = QPushButton(text)
            btn.clicked.connect(callback)
            actions.addWidget(btn)
        side.addLayout(actions)

        content = QVBoxLayout()
        body.addLayout(content, 4)

        content_hdr = QHBoxLayout()
        self.goal_heading = QLabel("Select a goal")
        self.goal_heading.setObjectName("heading")
        content_hdr.addWidget(self.goal_heading)
        content_hdr.addStretch()

        self.add_tab_btn = QPushButton("+ Add tab")
        self.add_tab_btn.clicked.connect(self.add_tab)
        content_hdr.addWidget(self.add_tab_btn)
        content.addLayout(content_hdr)

        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.render_steps)
        self.tabs.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(self.tab_menu)
        content.addWidget(self.tabs)

        self.tab_actions = QHBoxLayout()
        content.addLayout(self.tab_actions)

        self.progress = QLabel("")
        self.progress.setObjectName("muted")
        content.addWidget(self.progress)

        self.reload_goals()

    def ask_text(self, title: str, label: str, value: str = "") -> str | None:
        text, ok = QInputDialog.getText(self, title, label, text=value)
        return text.strip() if ok and text.strip() else None

    def current_goal(self) -> int | None:
        item = self.goal_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def reload_goals(self, selected: int | None = None):
        goals = self.store.goals(self.uid)
        self.goal_list.blockSignals(True)
        self.goal_list.clear()
        for goal in goals:
            item = QListWidgetItem(goal["title"])
            item.setData(Qt.ItemDataRole.UserRole, goal["id"])
            self.goal_list.addItem(item)
        self.goal_list.blockSignals(False)

        if goals:
            self.add_tab_btn.setEnabled(True)
            row = next((i for i, g in enumerate(goals) if g["id"] == selected), 0)
            self.goal_list.setCurrentRow(row)
        else:
            self.add_tab_btn.setEnabled(False)
            self.tabs.blockSignals(True)
            self.tabs.clear()
            self.tabs.blockSignals(False)
            self.goal_heading.setText("Add a goal to get started")
            self.progress.setText("")
            self.update_tab_actions()
        self.refresh_funds()

    def select_goal(self, _row: int):
        goal = self.current_goal()
        if not goal:
            return
        item = self.goal_list.currentItem()
        self.goal_heading.setText(item.text())
        self.reload_tabs()

    def reload_tabs(self, current_id: int | None = None):
        gid = self.current_goal()
        self.tabs.blockSignals(True)
        self.tabs.clear()
        if gid:
            for tab in self.store.tabs(gid):
                page = QWidget()
                page.setProperty("tab_id", tab["id"])
                self.tabs.addTab(page, tab["title"])
        self.tabs.blockSignals(False)

        if self.tabs.count():
            idx = next(
                (i for i in range(self.tabs.count()) if self.tabs.widget(i).property("tab_id") == current_id),
                0,
            )
            self.tabs.setCurrentIndex(idx)
        self.update_tab_actions()
        self.render_steps()

    def update_tab_actions(self):
        while self.tab_actions.count():
            item = self.tab_actions.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        has_tabs = self.tabs.count() > 0
        for text, callback in (("Rename tab", self.rename_tab), ("Delete tab", self.delete_tab)):
            btn = QPushButton(text)
            btn.setEnabled(has_tabs)
            btn.clicked.connect(callback)
            self.tab_actions.addWidget(btn)
        self.tab_actions.addStretch()

    def current_tab(self) -> int | None:
        page = self.tabs.currentWidget()
        return page.property("tab_id") if page else None

    def render_steps(self, *_):
        gid = self.current_goal()
        totals = self.store.totals(self.uid)
        remaining = totals["total_funds"] - totals["spent"]

        if gid:
            tab_titles = {t["id"]: t["title"] for t in self.store.tabs(gid)}
            for i in range(self.tabs.count()):
                tabid_i = self.tabs.widget(i).property("tab_id")
                steps = self.store.steps(tabid_i)
                affordable = sum(1 for s in steps if not s["done"] and s["cost"] <= remaining)
                original = tab_titles.get(tabid_i, "")
                self.tabs.setTabText(i, f"{original}  ·  {affordable} affordable")

        page = self.tabs.currentWidget()
        if not page:
            self.progress.setText("")
            self.refresh_funds()
            return

        old = page.layout()
        if old:
            while old.count():
                child = old.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            layout = old
        else:
            layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 12, 8, 8)

        tabid = self.current_tab()
        rows = self.store.steps(tabid)

        table = QTableWidget(len(rows), 5)
        table.setHorizontalHeaderLabels(["Done", "Step", "Cost", "Notes", "Deadline"])
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(lambda pos, t=table: self.step_menu(t, pos))

        table.horizontalHeader().setStretchLastSection(False)
        table.setColumnWidth(0, 60)
        table.setColumnWidth(2, 100)
        table.setColumnWidth(3, 210)
        table.setColumnWidth(4, 120)
        table.horizontalHeader().setSectionResizeMode(1, table.horizontalHeader().ResizeMode.Stretch)

        for i, step in enumerate(rows):
            check = QCheckBox()
            check.setChecked(bool(step["done"]))
            check.stateChanged.connect(
                lambda state, sid=step["id"]: self.set_done(sid, state == Qt.CheckState.Checked.value)
            )
            check_holder = QWidget()
            check_layout = QHBoxLayout(check_holder)
            check_layout.setContentsMargins(0, 0, 0, 0)
            check_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            check_layout.addWidget(check)
            table.setCellWidget(i, 0, check_holder)

            title = QLineEdit(step["title"])
            title.setFrame(False)
            title.editingFinished.connect(
                lambda w=title, sid=step["id"]: self.update_step(sid, "title", w.text())
            )

            cost = QDoubleSpinBox()
            cost.setRange(0, 1_000_000_000)
            cost.setDecimals(2)
            cost.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            cost.setValue(step["cost"])
            cost.setKeyboardTracking(False)
            cost.editingFinished.connect(
                lambda w=cost, sid=step["id"]: self.update_step(sid, "cost", w.value())
            )

            notes = QLineEdit(step["notes"])
            notes.setFrame(False)
            notes.setPlaceholderText("Optional notes")
            notes.editingFinished.connect(
                lambda w=notes, sid=step["id"]: self.update_step(sid, "notes", w.text())
            )

            deadline = QLineEdit(step["deadline"])
            deadline.setFrame(False)
            deadline.setPlaceholderText("YYYY-MM-DD")
            deadline.editingFinished.connect(
                lambda w=deadline, sid=step["id"]: self.update_step(sid, "deadline", w.text())
            )

            table.setCellWidget(i, 1, title)
            table.setCellWidget(i, 2, cost)
            table.setCellWidget(i, 3, notes)
            table.setCellWidget(i, 4, deadline)
            table.setRowHeight(i, 46)

            if not step["done"] and step["cost"] <= remaining:
                for widget in (title, cost, notes, deadline):
                    widget.setStyleSheet("background: #eef8f1; border-radius: 4px;")

        layout.addWidget(table)

        add_btn = QPushButton("+ Add step")
        add_btn.clicked.connect(self.add_step)
        layout.addWidget(add_btn, 0, Qt.AlignmentFlag.AlignLeft)

        done = sum(1 for s in rows if s["done"])
        self.progress.setText(f"{done} of {len(rows)} steps complete")
        self.refresh_funds()

    def refresh_funds(self):
        data = self.store.totals(self.uid)
        remaining = data["total_funds"] - data["spent"]
        self.funds_label.setText(
            f"Funds  {data['total_funds']:,.2f}     ·     "
            f"Spent  {data['spent']:,.2f}     ·     "
            f"Remaining  {remaining:,.2f}"
        )

    def set_funds(self):
        current = self.store.totals(self.uid)["total_funds"]
        val, ok = QInputDialog.getDouble(
            self, "Total funds", "Set total funds", current, 0, 1_000_000_000, 2
        )
        if ok:
            with self.store.db:
                self.store.db.execute(
                    "UPDATE users SET total_funds = ? WHERE id = ?",
                    (val, self.uid),
                )
            self.render_steps()

    def add_goal(self):
        title = self.ask_text("Add goal", "Goal name")
        if title:
            order = len(self.store.goals(self.uid))
            with self.store.db:
                cur = self.store.db.execute(
                    "INSERT INTO goals(user_id, title, order_index) VALUES(?, ?, ?)",
                    (self.uid, title, order),
                )
                gid = cur.lastrowid
            self.reload_goals(gid)

    def rename_goal(self):
        gid = self.current_goal()
        if not gid:
            return
        item = self.goal_list.currentItem()
        title = self.ask_text("Rename goal", "Goal name", item.text())
        if title:
            with self.store.db:
                self.store.db.execute(
                    "UPDATE goals SET title = ? WHERE id = ? AND user_id = ?",
                    (title, gid, self.uid),
                )
            self.reload_goals(gid)

    def delete_goal(self):
        gid = self.current_goal()
        if not gid:
            return
        reply = QMessageBox.question(
            self,
            "Delete goal",
            "Delete this goal and all its tabs and steps?",
        )
        if reply == QMessageBox.StandardButton.Yes:
            with self.store.db:
                self.store.db.execute(
                    "DELETE FROM goals WHERE id = ? AND user_id = ?",
                    (gid, self.uid),
                )
            self.reload_goals()

    def move_goal(self, delta: int):
        row = self.goal_list.currentRow()
        goals = self.store.goals(self.uid)
        other = row + delta
        if 0 <= row < len(goals) and 0 <= other < len(goals):
            a, b = goals[row], goals[other]
            with self.store.db:
                self.store.db.execute(
                    "UPDATE goals SET order_index = ? WHERE id = ?",
                    (b["order_index"], a["id"]),
                )
                self.store.db.execute(
                    "UPDATE goals SET order_index = ? WHERE id = ?",
                    (a["order_index"], b["id"]),
                )
            self.reload_goals(a["id"])

    def goal_menu(self, pos):
        row = self.goal_list.indexAt(pos).row()
        if row < 0:
            return
        self.goal_list.setCurrentRow(row)
        menu = QMenu(self)
        rename = menu.addAction("Rename")
        menu.addAction("Move up", lambda: self.move_goal(-1)).setEnabled(row > 0)
        menu.addAction("Move down", lambda: self.move_goal(1)).setEnabled(
            row < self.goal_list.count() - 1
        )
        delete = menu.addAction("Delete")
        chosen = menu.exec(self.goal_list.mapToGlobal(pos))
        if chosen == rename:
            self.rename_goal()
        elif chosen == delete:
            self.delete_goal()

    def add_tab(self):
        gid = self.current_goal()
        if not gid:
            return
        title = self.ask_text("Add tab", "Tab name")
        if title:
            order = len(self.store.tabs(gid))
            with self.store.db:
                cur = self.store.db.execute(
                    "INSERT INTO tabs(goal_id, title, order_index) VALUES(?, ?, ?)",
                    (gid, title, order),
                )
                tid = cur.lastrowid
            self.reload_tabs(tid)

    def rename_tab(self):
        tid = self.current_tab()
        if not tid:
            return
        current_title = self.tabs.tabText(self.tabs.currentIndex()).split("  ·")[0]
        title = self.ask_text("Rename tab", "Tab name", current_title)
        if title:
            with self.store.db:
                self.store.db.execute(
                    "UPDATE tabs SET title = ? WHERE id = ? AND goal_id = ?",
                    (title, tid, self.current_goal()),
                )
            self.reload_tabs(tid)

    def delete_tab(self):
        tid = self.current_tab()
        if not tid:
            return
        reply = QMessageBox.question(
            self,
            "Delete tab",
            "Delete this tab and all its steps?",
        )
        if reply == QMessageBox.StandardButton.Yes:
            with self.store.db:
                self.store.db.execute(
                    "DELETE FROM tabs WHERE id = ? AND goal_id = ?",
                    (tid, self.current_goal()),
                )
            self.reload_tabs()

    def move_tab(self, delta: int):
        gid = self.current_goal()
        row = self.tabs.currentIndex()
        tabs = self.store.tabs(gid)
        other = row + delta
        if 0 <= row < len(tabs) and 0 <= other < len(tabs):
            a, b = tabs[row], tabs[other]
            with self.store.db:
                self.store.db.execute(
                    "UPDATE tabs SET order_index = ? WHERE id = ?",
                    (b["order_index"], a["id"]),
                )
                self.store.db.execute(
                    "UPDATE tabs SET order_index = ? WHERE id = ?",
                    (a["order_index"], b["id"]),
                )
            self.reload_tabs(a["id"])

    def tab_menu(self, pos):
        index = self.tabs.tabBar().tabAt(pos)
        if index < 0:
            return
        self.tabs.setCurrentIndex(index)
        menu = QMenu(self)
        rename = menu.addAction("Rename tab")
        menu.addAction("Move left", lambda: self.move_tab(-1)).setEnabled(index > 0)
        menu.addAction("Move right", lambda: self.move_tab(1)).setEnabled(
            index < self.tabs.count() - 1
        )
        delete = menu.addAction("Delete tab")
        chosen = menu.exec(self.tabs.tabBar().mapToGlobal(pos))
        if chosen == rename:
            self.rename_tab()
        elif chosen == delete:
            self.delete_tab()

    def add_step(self):
        tid = self.current_tab()
        if not tid:
            return
        title = self.ask_text("Add step", "Step title")
        if title:
            order = len(self.store.steps(tid))
            with self.store.db:
                self.store.db.execute(
                    "INSERT INTO steps(tab_id, title, order_index) VALUES(?, ?, ?)",
                    (tid, title, order),
                )
            self.render_steps()

    def update_step(self, sid: int, field: str, value):
        if field == "title" and not str(value).strip():
            return
        gid = self.current_goal()
        with self.store.db:
            self.store.db.execute(
                f"UPDATE steps SET {field} = ? WHERE id = ? AND tab_id IN (SELECT id FROM tabs WHERE goal_id = ?)",
                (value, sid, gid),
            )
        self.render_steps()

    def set_done(self, sid: int, done: bool):
        status = "Done" if done else "Not Started"
        with self.store.db:
            self.store.db.execute(
                "UPDATE steps SET done = ?, status = ? WHERE id = ? AND tab_id IN (SELECT id FROM tabs WHERE goal_id = ?)",
                (int(done), status, sid, self.current_goal()),
            )
        self.render_steps()

    def delete_step(self, sid: int):
        with self.store.db:
            self.store.db.execute(
                "DELETE FROM steps WHERE id = ? AND tab_id IN (SELECT id FROM tabs WHERE goal_id = ?)",
                (sid, self.current_goal()),
            )
        self.render_steps()

    def move_step(self, sid: int, delta: int):
        tid = self.current_tab()
        rows = self.store.steps(tid)
        index = next((i for i, s in enumerate(rows) if s["id"] == sid), -1)
        other = index + delta
        if 0 <= index < len(rows) and 0 <= other < len(rows):
            a, b = rows[index], rows[other]
            with self.store.db:
                self.store.db.execute(
                    "UPDATE steps SET order_index = ? WHERE id = ?",
                    (b["order_index"], a["id"]),
                )
                self.store.db.execute(
                    "UPDATE steps SET order_index = ? WHERE id = ?",
                    (a["order_index"], b["id"]),
                )
            self.render_steps()

    def step_menu(self, table: QTableWidget, pos):
        row = table.rowAt(pos.y())
        if row < 0:
            return
        sid = self.store.steps(self.current_tab())[row]["id"]
        menu = QMenu(self)
        menu.addAction("Move up", lambda: self.move_step(sid, -1)).setEnabled(row > 0)
        menu.addAction("Move down", lambda: self.move_step(sid, 1)).setEnabled(
            row < table.rowCount() - 1
        )
        menu.addSeparator()
        menu.addAction("Delete step", lambda: self.delete_step(sid))
        menu.exec(table.viewport().mapToGlobal(pos))

    def backup(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose backup folder")
        if folder:
            self.store.db.commit()
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            target = Path(folder) / f"happen-backup-{timestamp}.db"
            with sqlite3.connect(target) as dst:
                self.store.db.backup(dst)
            QMessageBox.information(
                self, "Backup complete", f"Saved backup to:\n{target}"
            )


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(QIcon(str(asset_path("assets/happen.ico"))))
    app.setStyleSheet(STYLESHEET)

    store = Store(database_path())
    login = AuthDialog(store)
    if login.exec() != QDialog.DialogCode.Accepted:
        return 0

    window = MainWindow(store, login.user)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
