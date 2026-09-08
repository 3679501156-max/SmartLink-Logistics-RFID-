import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import queue
import time
from datetime import datetime
from typing import Optional, Dict

from core.database import DatabaseManager
from core.threads import RFIDReaderThread

# 注册窗口类
class RegistrationWindow(tk.Toplevel):
    def __init__(self, parent, db_manager: DatabaseManager, card_uid: str, on_registered: callable, on_cancel: callable):
        super().__init__(parent)
        self.db_manager = db_manager
        self.card_uid = card_uid
        self.on_registered = on_registered
        self.on_cancel = on_cancel
        self.is_closed = False

        self.title(f"注册新选手 - {card_uid}")
        self.geometry("400x450")
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close_window)
        
        self._setup_widgets()
        
    def _setup_widgets(self):
        form = tk.LabelFrame(self, text="选手信息", font=("微软雅黑", 10))
        form.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.entries = {}
        fields = [("姓名*", "name"), ("性别", "gender"), ("年龄", "age"), ("队伍", "team"), ("电话", "phone")]
        
        for i, (label, key) in enumerate(fields):
            tk.Label(form, text=label).grid(row=i, column=0, padx=5, pady=5)
            if key == "gender":
                self.gender_var = tk.StringVar(value="男")
                f = tk.Frame(form)
                f.grid(row=i, column=1, padx=5, pady=5)
                tk.Radiobutton(f, text="男", variable=self.gender_var, value="男").pack(side=tk.LEFT)
                tk.Radiobutton(f, text="女", variable=self.gender_var, value="女").pack(side=tk.LEFT)
            else:
                e = tk.Entry(form)
                e.grid(row=i, column=1, padx=5, pady=5)
                self.entries[key] = e
        
        tk.Button(self, text="注册", command=self._register, bg="#27ae60", fg="white").pack(pady=10)

    def _register(self):
        success, msg, _ = self.db_manager.register_participant(
            self.card_uid, self.entries['name'].get(), self.gender_var.get(), 
            int(self.entries['age'].get() or 0), self.entries['team'].get(), self.entries['phone'].get()
        )
        if success:
            self.is_closed = True
            self.destroy()
            if self.on_registered: self.on_registered()
        else:
            messagebox.showerror("错误", msg)
        
    def _close_window(self):
        self.is_closed = True
        self.destroy()
        if self.on_cancel: self.on_cancel()

# 主界面类
class OrienteeringUI:
    def __init__(self, db_manager: DatabaseManager, config: Dict):
        self.root = tk.Tk()
        self.root.title("定向越野管理系统 v2.1")
        self.root.geometry("1000x750")
        
        self.db_manager = db_manager
        self.config = config
        self.message_queue = queue.Queue()
        
        self._setup_ui()
        self._process_messages()
        self._start_rfid_thread()
        
    def _setup_ui(self):
        # 顶部标题
        tk.Label(self.root, text="定向越野管理系统", font=("微软雅黑", 20)).pack(pady=10)
        
        # Notebook布局
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 选项卡：注册、监控、管理
        self.reg_tab = ttk.Frame(notebook)
        notebook.add(self.reg_tab, text="选手注册")
        
        # 注册列表
        self.reg_tree = ttk.Treeview(self.reg_tab, columns=("姓名", "卡号"), show="headings")
        self.reg_tree.heading("姓名", text="姓名")
        self.reg_tree.heading("卡号", text="卡号")
        self.reg_tree.pack(fill=tk.BOTH, expand=True)
        
        # 监控页面
        self.monitor_tab = ttk.Frame(notebook)
        notebook.add(self.monitor_tab, text="实时监控")
        self.log_text = tk.Text(self.monitor_tab)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # 操作按钮
        tk.Button(self.root, text="开始比赛", command=self._start_race).pack(side=tk.LEFT, padx=20, pady=10)
        tk.Button(self.root, text="结束比赛", command=self._end_race).pack(side=tk.LEFT, padx=20, pady=10)
        
    def _start_rfid_thread(self):
        self.rfid_thread = RFIDReaderThread(
            self.db_manager, self.message_queue,
            self.config['ip'], self.config['port']
        )
        self.rfid_thread.daemon = True
        self.rfid_thread.start()
        
    def _process_messages(self):
        try:
            while True:
                msg_type, data = self.message_queue.get_nowait()
                if msg_type == "register_request":
                    self._handle_register(data)
                elif msg_type == "punch":
                    self.log_text.insert(tk.END, f"打卡: {data['name']} 在点{data['antenna']} 时间{data['time']}\n")
        except queue.Empty:
            pass
        self.root.after(100, self._process_messages)
        
    def _handle_register(self, card_uid):
        if not hasattr(self, 'reg_window') or not self.reg_window:
            self.reg_window = RegistrationWindow(
                self.root, self.db_manager, card_uid,
                lambda: setattr(self, 'reg_window', None),
                lambda: setattr(self, 'reg_window', None)
            )

    def _start_race(self):
        self.rfid_thread.set_mode("race")
        self.rfid_thread.start_race()
        
    def _end_race(self):
        self.rfid_thread.stop_race()
        
    def run(self):
        self.root.mainloop()
