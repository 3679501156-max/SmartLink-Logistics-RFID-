import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
from datetime import datetime, timedelta
import sqlite3
import socket
import queue
import struct
import csv
import json
import os
from typing import Optional, Dict, List, Tuple

# ==================== 配置部分 ====================
IP = '192.168.0.160'  # RFID读卡器IP
PORT = 4001
DB_FILE = "bus_card.db"


# ==================== RFID通信模块 ====================
class RFIDWiFiReader:
    """RFID读卡器通信类（基于定向越野系统代码优化）"""

    def __init__(self, ip: str = IP, port: int = PORT):
        self.ip = ip
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.current_antenna = 1
        self.connected = False

    def connect(self) -> bool:
        """连接到WiFi模块"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(3)
            self.sock.connect((self.ip, self.port))
            self.connected = True
            return True
        except Exception as e:
            print(f"连接失败: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        if self.sock:
            self.sock.close()
            self.sock = None
            self.connected = False

    def calculate_checksum(self, bytes_list: List[int]) -> int:
        """计算异或校验码"""
        checksum = 0
        for byte in bytes_list:
            checksum ^= byte
        return checksum

    def build_command(self, command_low: int, command_high: int, data_bytes: List[int]) -> bytes:
        """
        构建指令
        格式: AA BB [数据长度] 00 00 [命令低字节] [命令高字节] [数据包] [校验码]
        """
        # 命令头
        cmd = [0xAA, 0xBB]

        # 数据长度: 设备号(2) + 命令码(2) + 数据包长度 + 校验码(1)
        data_len = 2 + 2 + len(data_bytes) + 1
        cmd.extend([data_len & 0xFF, (data_len >> 8) & 0xFF])  # 低位在前

        # 设备号 (00 00)
        cmd.extend([0x00, 0x00])

        # 命令码 (低位在前)
        cmd.extend([command_low, command_high])

        # 数据包
        cmd.extend(data_bytes)

        # 计算校验码 (从命令码开始)
        checksum_bytes = [command_low, command_high] + data_bytes
        checksum = self.calculate_checksum(checksum_bytes)
        cmd.append(checksum)

        return bytes(cmd)

    def send_command(self, command: bytes, description: str = "", timeout: float = 2.0) -> Optional[bytes]:
        """发送命令并接收响应"""
        if not self.sock or not self.connected:
            print("未连接到设备")
            return None

        try:
            # 清空缓冲区
            self.sock.settimeout(0.1)
            try:
                self.sock.recv(4096)
            except:
                pass

            # 发送命令
            self.sock.sendall(command)

            # 接收响应
            self.sock.settimeout(timeout)
            response = self.sock.recv(1024)

            return response

        except socket.timeout:
            print(f"[超时] {description} 等待响应超时")
            return None
        except Exception as e:
            print(f"[错误] {description} 发送失败: {e}")
            return None

    def recv_frame(self, timeout: float = 1.0) -> Optional[bytes]:
        """被动接收一帧响应数据"""
        if not self.sock or not self.connected:
            return None
        try:
            self.sock.settimeout(timeout)
            data = self.sock.recv(1024)
            return data if data else None
        except socket.timeout:
            return None
        except Exception as e:
            print(f"接收数据错误: {e}")
            return None

    def select_antenna(self, antenna_no: int) -> bool:
        """选择天线"""
        if not (1 <= antenna_no <= 8):
            print(f"天线号无效: {antenna_no}")
            return False

        # 命令码: 0xFF 0x11 (天线切换命令)
        device_antenna = antenna_no - 1  # 设备通常使用 0~7 编号
        command = self.build_command(0xFF, 0x11, [device_antenna])
        response = self.send_command(command, f"切换到天线{antenna_no}")

        if response:
            parsed = self.parse_response(response)
            if parsed and parsed.get('status_code') == 0x00:
                self.current_antenna = antenna_no
                time.sleep(0.05)  # 切换天线后给硬件一点稳定时间
                return True
        return False

    def search_card(self) -> Optional[bytes]:
        """寻卡"""
        # 命令码: 0x01 0x02 (寻卡命令)
        command = self.build_command(0x01, 0x02, [0x52])  # 0x52: 寻所有卡
        return self.send_command(command, "寻卡")

    def anticollision_read_uid(self) -> Optional[bytes]:
        """防碰撞读UID"""
        command = self.build_command(0x02, 0x02, [0x04])  # 参数
        return self.send_command(command, "读UID")

    def parse_response(self, response: bytes) -> Optional[Dict]:
        """解析响应数据"""
        if len(response) < 9:
            return None

        # 验证命令头
        if response[0:2] != b'\xAA\xBB':
            return None

        # 获取数据长度
        data_len = response[2] + (response[3] << 8)

        # 获取命令码
        cmd_low = response[6]
        cmd_high = response[7]
        command = (cmd_high << 8) | cmd_low

        # 获取状态码
        status = response[8]

        result = {
            'command': f"0x{command:04X}",
            'status': '成功' if status == 0x00 else '失败',
            'status_code': status,
            'raw_data': response,
            'data_length': len(response)
        }

        # 根据不同命令解析数据
        if command == 0x11FF:  # 天线切换响应
            result['operation'] = '天线切换'

        elif command == 0x0201:  # 寻卡响应
            result['operation'] = '寻卡'
            if status == 0x00 and len(response) >= 12:
                card_type = response[9:11]
                result['card_type'] = card_type.hex().upper()

        elif command == 0x0202:  # 读UID响应
            result['operation'] = '读UID'
            if status == 0x00 and len(response) >= 13:
                # UID在9-13字节（4字节UID）
                uid = response[9:13]
                result['uid'] = uid.hex().upper()

        return result

    def read_card_uid(self) -> Optional[str]:
        """读取卡片UID（完整流程）"""
        # 寻卡
        search_response = self.search_card()
        if not search_response:
            return None

        search_data = self.parse_response(search_response)
        if not search_data or search_data['status'] != '成功':
            return None

        # 读UID
        uid_response = self.anticollision_read_uid()
        if not uid_response:
            return None

        uid_data = self.parse_response(uid_response)
        if uid_data and 'uid' in uid_data:
            return uid_data['uid']

        return None


# ==================== 数据库模块 ====================
class DatabaseManager:
    """数据库管理类（公交车刷卡系统专用）"""

    def __init__(self, db_file: str = DB_FILE):
        self.db_file = db_file
        self.init_database()

    def init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        # 创建卡片信息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS card_info (
                uid TEXT PRIMARY KEY,
                identity TEXT NOT NULL, 
                balance FLOAT DEFAULT 0.0,
                register_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 创建交易记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transaction_record (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid TEXT NOT NULL,
                trans_type TEXT NOT NULL,
                amount FLOAT NOT NULL,
                trans_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT '成功',
                FOREIGN KEY (uid) REFERENCES card_info(uid)
            )
        ''')

        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_card_uid ON card_info(uid)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trans_time ON transaction_record(trans_time)')

        conn.commit()
        conn.close()

    def query_card(self, uid: str) -> Optional[Tuple]:
        """查询卡片信息"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute("SELECT identity, balance FROM card_info WHERE uid=?", (uid,))
            res = cursor.fetchone()
            conn.close()
            return res
        except Exception as e:
            print(f"查询卡片失败: {e}")
            return None

    def insert_card(self, uid: str, identity: str, balance: float = 0.0) -> bool:
        """新增卡片信息，并记录注册交易"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()

            # 插入卡片信息
            cursor.execute("INSERT INTO card_info (uid, identity, balance) VALUES (?, ?, ?)",
                           (uid, identity, balance))

            # 插入注册交易记录
            cursor.execute("""INSERT INTO transaction_record 
                           (uid, trans_type, amount, status) 
                           VALUES (?, ?, ?, ?)""",
                           (uid, '注册', 0.0, '成功'))

            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            # 卡片已存在
            return False
        except Exception as e:
            print(f"新增卡片失败: {e}")
            return False

    def update_balance(self, uid: str, amount: float) -> bool:
        """更新卡片余额"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute("UPDATE card_info SET balance=balance+? WHERE uid=?", (amount, uid))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"更新余额失败: {e}")
            return False

    def add_transaction_record(self, uid: str, trans_type: str, amount: float, status: str = '成功'):
        """新增交易记录（充值/扣费）"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()

            # 扣费金额转为负数，便于显示
            if trans_type == '扣费':
                amount = -abs(amount)

            cursor.execute("""
                INSERT INTO transaction_record 
                (uid, trans_type, amount, status, trans_time) 
                VALUES (?, ?, ?, ?, datetime('now', 'localtime'))
            """, (uid, trans_type, amount, status))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"添加交易记录失败: {e}")
            return False

    def query_transaction_records(self, uid: str = None, start_date: str = None, end_date: str = None):
        """查询交易记录（支持按UID、时间筛选）"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()

            # 构建查询条件
            query = """
                SELECT id, uid, trans_type, amount, trans_time, status 
                FROM transaction_record 
                WHERE 1=1
            """
            params = []

            if uid:
                query += " AND uid = ?"
                params.append(uid)

            if start_date:
                query += " AND DATE(trans_time) >= ?"
                params.append(start_date)

            if end_date:
                query += " AND DATE(trans_time) <= ?"
                params.append(end_date)

            # 按时间倒序排列
            query += " ORDER BY trans_time DESC"

            cursor.execute(query, params)
            records = cursor.fetchall()
            conn.close()
            return records
        except Exception as e:
            print(f"查询交易记录失败: {e}")
            return []

    def get_all_cards(self) -> List[Dict]:
        """获取所有卡片信息"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT uid, identity, balance, register_time 
                FROM card_info 
                ORDER BY register_time DESC
            ''')

            cards = cursor.fetchall()
            conn.close()

            result = []
            for card in cards:
                result.append({
                    'uid': card[0],
                    'identity': card[1],
                    'balance': card[2],
                    'register_time': card[3]
                })

            return result
        except Exception as e:
            print(f"获取卡片列表失败: {e}")
            return []

    def clear_all_data(self):
        """清除所有数据"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM transaction_record")
            cursor.execute("DELETE FROM card_info")
            cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('card_info', 'transaction_record')")
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"清除数据失败: {e}")
            return False


# ==================== RFID读取线程 ====================
class RFIDReaderThread(threading.Thread):
    """RFID读取线程（公交车刷卡系统专用）"""

    def __init__(self, db_manager: DatabaseManager, message_queue: queue.Queue,
                 ip: str = IP, port: int = PORT):
        super().__init__()
        self.db_manager = db_manager
        self.message_queue = message_queue
        self.ip = ip
        self.port = port
        self.running = True
        self.reader: Optional[RFIDWiFiReader] = None
        self.last_read = {}  # 用于去重: {card_uid: timestamp}

    def run(self):
        """线程主函数"""
        try:
            self.reader = RFIDWiFiReader(self.ip, self.port)
            if not self.reader.connect():
                self.message_queue.put(("error", "无法连接到RFID读卡器"))
                return

            self.message_queue.put(("info", "已连接到RFID读卡器"))

            while self.running:
                self._process_cards()
                time.sleep(0.1)  # 降低CPU占用

        except Exception as e:
            self.message_queue.put(("error", f"线程错误: {str(e)}"))
        finally:
            if self.reader:
                self.reader.disconnect()

    def _process_cards(self):
        """处理卡片读取"""
        try:
            if not self.reader or not self.reader.connected:
                return

            # 读取卡片UID
            card_uid = self.reader.read_card_uid()
            if not card_uid:
                return

            # 防抖检查：同一卡片2秒内不重复处理
            current_time = time.time()
            if card_uid in self.last_read and current_time - self.last_read[card_uid] < 2:
                return

            self.last_read[card_uid] = current_time

            # 检查卡片是否已注册
            card_info = self.db_manager.query_card(card_uid)

            if card_info:
                # 卡片已注册，执行扣费逻辑
                identity, balance = card_info
                self._process_deduction(card_uid, identity, balance)
            else:
                # 卡片未注册，发送注册请求
                self.message_queue.put(("register_request", card_uid))

        except Exception as e:
            print(f"处理卡片错误: {e}")

    def _process_deduction(self, card_uid: str, identity: str, balance: float):
        """处理扣费逻辑"""
        # 根据身份确定扣费金额
        fee_map = {"老人": 0.0, "小孩": 1.0, "青年": 2.0}
        fee = fee_map.get(identity, 2.0)

        if fee == 0.0:
            # 免费乘车
            self.db_manager.add_transaction_record(card_uid, '扣费', 0.0, '免费')
            self.message_queue.put(("deduct_success", {
                'uid': card_uid,
                'identity': identity,
                'fee': fee,
                'balance': balance,
                'message': f"{identity}卡免费乘车"
            }))
            return

        # 检查余额是否足够
        if balance < fee:
            self.db_manager.add_transaction_record(card_uid, '扣费', fee, '失败-余额不足')
            self.message_queue.put(("deduct_failed", {
                'uid': card_uid,
                'identity': identity,
                'fee': fee,
                'balance': balance,
                'message': f"余额不足，需要{fee}元，当前余额{balance}元"
            }))
            return

        # 执行扣费
        if self.db_manager.update_balance(card_uid, -fee):
            new_balance = balance - fee
            self.db_manager.add_transaction_record(card_uid, '扣费', fee, '成功')
            self.message_queue.put(("deduct_success", {
                'uid': card_uid,
                'identity': identity,
                'fee': fee,
                'balance': new_balance,
                'message': f"扣费成功: {fee}元"
            }))
        else:
            self.db_manager.add_transaction_record(card_uid, '扣费', fee, '失败')
            self.message_queue.put(("deduct_failed", {
                'uid': card_uid,
                'identity': identity,
                'fee': fee,
                'balance': balance,
                'message': f"扣费失败"
            }))

    def stop(self):
        """停止线程"""
        self.running = False


# ==================== 注册窗口 ====================
class RegistrationWindow(tk.Toplevel):
    """注册新卡片窗口"""

    def __init__(self, parent, db_manager: DatabaseManager, card_uid: str,
                 on_registered: callable):
        super().__init__(parent)
        self.parent = parent
        self.db_manager = db_manager
        self.card_uid = card_uid
        self.on_registered = on_registered

        self.title(f"卡片注册 - UID: {card_uid}")
        self.geometry("400x300")
        self.resizable(False, False)

        # 设置窗口始终在最前面
        self.transient(parent)
        self.grab_set()

        self.setup_widgets()

    def setup_widgets(self):
        """设置控件"""
        # 主容器
        main_frame = tk.Frame(self, bg="#f0f0f0")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 标题
        tk.Label(main_frame, text="📋 卡片注册", font=("微软雅黑", 16, "bold"),
                 bg="#f0f0f0", fg="#2c3e50").pack(pady=(0, 20))

        # UID显示
        uid_frame = tk.Frame(main_frame, bg="#f0f0f0")
        uid_frame.pack(fill=tk.X, pady=5)
        tk.Label(uid_frame, text="卡号:", font=("微软雅黑", 11), bg="#f0f0f0").pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(uid_frame, text=self.card_uid, font=("Consolas", 12, "bold"),
                 bg="#f0f0f0", fg="#3498db").pack(side=tk.LEFT)

        # 身份选择
        identity_frame = tk.Frame(main_frame, bg="#f0f0f0")
        identity_frame.pack(fill=tk.X, pady=10)
        tk.Label(identity_frame, text="身份类型:", font=("微软雅黑", 11), bg="#f0f0f0").pack(side=tk.LEFT, padx=(0, 10))

        self.identity_var = tk.StringVar(value="青年")
        identity_options = tk.Frame(identity_frame, bg="#f0f0f0")
        identity_options.pack(side=tk.LEFT)

        identities = [("老人", "#e74c3c"), ("小孩", "#f39c12"), ("青年", "#3498db")]
        for identity, color in identities:
            tk.Radiobutton(identity_options, text=identity, variable=self.identity_var,
                           value=identity, font=("微软雅黑", 10), bg="#f0f0f0",
                           selectcolor=color).pack(side=tk.LEFT, padx=5)

        # 初始余额
        balance_frame = tk.Frame(main_frame, bg="#f0f0f0")
        balance_frame.pack(fill=tk.X, pady=10)
        tk.Label(balance_frame, text="初始余额:", font=("微软雅黑", 11), bg="#f0f0f0").pack(side=tk.LEFT, padx=(0, 10))

        self.balance_var = tk.StringVar(value="0.0")
        tk.Entry(balance_frame, textvariable=self.balance_var, width=15,
                 font=("微软雅黑", 11), bd=1, relief="solid").pack(side=tk.LEFT)

        # 按钮
        button_frame = tk.Frame(main_frame, bg="#f0f0f0")
        button_frame.pack(pady=20)

        # 修改按钮部分，使其更醒目
        tk.Button(
            button_frame,
            text="✅ 确认注册",
            font=("微软雅黑", 12, "bold"),  # 加粗字体
            bg="#27ae60",
            fg="white",
            padx=30,
            pady=8,
            bd=0,
            relief="raised",  # 添加立体效果
            cursor="hand2",  # 鼠标悬停手型
            command=self._do_register
        ).pack(side=tk.LEFT, padx=10)

        tk.Button(
            button_frame, text="❌ 取消", font=("微软雅黑", 11),
            bg="#95a5a6", fg="white", padx=20, pady=5, bd=0,
            command=self.destroy
        ).pack(side=tk.LEFT, padx=10)

    def _do_register(self):
        """注册卡片"""
        identity = self.identity_var.get()

        try:
            balance = float(self.balance_var.get())
            if balance < 0:
                messagebox.showerror("错误", "余额不能为负数！", parent=self)
                return
        except ValueError:
            messagebox.showerror("错误", "请输入有效的金额！", parent=self)
            return

        # 注册卡片
        success = self.db_manager.insert_card(self.card_uid, identity, balance)

        if success:
            messagebox.showinfo("成功", f"{identity}卡注册成功！\n初始余额: {balance}元", parent=self)

            # 执行回调
            if self.on_registered:
                self.on_registered(self.card_uid, identity, balance)

            self.destroy()
        else:
            messagebox.showerror("失败", "卡片已存在或注册失败！", parent=self)


# ==================== 充值窗口 ====================
class RechargeWindow(tk.Toplevel):
    """卡片充值窗口 - 修改为可以在窗口中刷卡充值"""

    def __init__(self, parent, db_manager: DatabaseManager, on_recharged: callable = None):
        super().__init__(parent)
        self.parent = parent
        self.db_manager = db_manager
        self.on_recharged = on_recharged

        # 当前读取的卡片信息
        self.card_uid = None
        self.current_balance = 0.0
        self.card_identity = "未知"

        self.title("卡片充值")
        self.geometry("500x600")
        self.resizable(False, False)

        # 设置窗口始终在最前面
        self.transient(parent)
        self.grab_set()

        # 设置刷卡处理标志
        self.waiting_for_card = True

        self.setup_widgets()

    def setup_widgets(self):
        """设置控件"""
        # 主容器
        main_frame = tk.Frame(self, bg="#f0f0f0")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=25, pady=25)

        # 标题
        tk.Label(main_frame, text="💰 卡片充值", font=("微软雅黑", 16, "bold"),
                 bg="#f0f0f0", fg="#2c3e50").pack(pady=(0, 20))

        # 刷卡提示区域
        self.card_status_frame = tk.LabelFrame(main_frame, text="请刷卡", font=("微软雅黑", 12),
                                               bg="#f0f0f0", bd=2, relief="solid", padx=15, pady=15)
        self.card_status_frame.pack(fill=tk.X, pady=10)

        # 卡片信息显示
        self.card_info_label = tk.Label(
            self.card_status_frame,
            text="请将卡片靠近读卡器...",
            font=("微软雅黑", 11),
            bg="#f0f0f0",
            fg="#7f8c8d",
            height=3
        )
        self.card_info_label.pack(fill=tk.X)

        # 卡片详细信息
        self.detail_frame = tk.Frame(main_frame, bg="#f0f0f0")
        self.detail_frame.pack(fill=tk.X, pady=10)

        # UID显示
        uid_frame = tk.Frame(self.detail_frame, bg="#f0f0f0")
        uid_frame.pack(fill=tk.X, pady=5)
        tk.Label(uid_frame, text="卡号:", font=("微软雅黑", 10), bg="#f0f0f0",
                 width=8, anchor="w").pack(side=tk.LEFT)
        self.uid_label = tk.Label(uid_frame, text="未读取", font=("Consolas", 10),
                                  bg="#f0f0f0", fg="#3498db")
        self.uid_label.pack(side=tk.LEFT)

        # 身份显示
        identity_frame = tk.Frame(self.detail_frame, bg="#f0f0f0")
        identity_frame.pack(fill=tk.X, pady=5)
        tk.Label(identity_frame, text="身份:", font=("微软雅黑", 10), bg="#f0f0f0",
                 width=8, anchor="w").pack(side=tk.LEFT)
        self.identity_label = tk.Label(identity_frame, text="未知", font=("微软雅黑", 10),
                                       bg="#f0f0f0", fg="#e67e22")
        self.identity_label.pack(side=tk.LEFT)

        # 余额显示
        balance_frame = tk.Frame(self.detail_frame, bg="#f0f0f0")
        balance_frame.pack(fill=tk.X, pady=5)
        tk.Label(balance_frame, text="余额:", font=("微软雅黑", 10), bg="#f0f0f0",
                 width=8, anchor="w").pack(side=tk.LEFT)
        self.balance_label = tk.Label(balance_frame, text="0.00 元", font=("微软雅黑", 10, "bold"),
                                      bg="#f0f0f0", fg="#27ae60")
        self.balance_label.pack(side=tk.LEFT)

        # 充值金额
        amount_frame = tk.Frame(main_frame, bg="#f0f0f0")
        amount_frame.pack(fill=tk.X, pady=15)

        tk.Label(amount_frame, text="充值金额:", font=("微软雅黑", 11),
                 bg="#f0f0f0", width=10, anchor="w").pack(side=tk.LEFT)

        self.amount_var = tk.StringVar(value="10.0")
        self.amount_entry = tk.Entry(amount_frame, textvariable=self.amount_var,
                                     width=15, font=("微软雅黑", 11), bd=1, relief="solid",
                                     state="disabled")  # 初始禁用
        self.amount_entry.pack(side=tk.LEFT)
        tk.Label(amount_frame, text="元", font=("微软雅黑", 11),
                 bg="#f0f0f0").pack(side=tk.LEFT, padx=5)

        # 快捷充值按钮（初始禁用）
        quick_frame = tk.LabelFrame(main_frame, text="快捷充值", font=("微软雅黑", 10),
                                    bg="#f0f0f0", bd=1, relief="solid")
        quick_frame.pack(fill=tk.X, pady=10)

        amounts = [10, 20, 50, 100, 200]
        self.quick_buttons = []
        for amount in amounts:
            btn = tk.Button(quick_frame, text=f"{amount}元", font=("微软雅黑", 10),
                            bg="#3498db", fg="white", padx=10, pady=5, bd=0,
                            command=lambda a=amount: self.set_amount(a),
                            state="disabled")  # 初始禁用
            btn.pack(side=tk.LEFT, padx=5, pady=5)
            self.quick_buttons.append(btn)

        # 按钮
        button_frame = tk.Frame(main_frame, bg="#f0f0f0")
        button_frame.pack(pady=20)

        # 充值按钮初始禁用
        self.recharge_button = tk.Button(
            button_frame, text="✅ 确认充值", font=("微软雅黑", 12),
            bg="#27ae60", fg="white", padx=25, pady=8, bd=0,
            command=self._do_recharge,
            state="disabled"  # 初始禁用
        )
        self.recharge_button.pack(side=tk.LEFT, padx=15)

        tk.Button(
            button_frame, text="❌ 关闭", font=("微软雅黑", 12),
            bg="#95a5a6", fg="white", padx=25, pady=8, bd=0,
            command=self.destroy
        ).pack(side=tk.LEFT, padx=15)

    def set_amount(self, amount: float):
        """设置充值金额"""
        self.amount_var.set(str(amount))

    def handle_card_read(self, card_uid: str):
        """处理卡片读取"""
        if not self.winfo_exists():
            return

        # 检查卡片是否已注册
        card_info = self.db_manager.query_card(card_uid)

        if not card_info:
            # 卡片未注册
            self.card_info_label.config(
                text="⚠️ 卡片未注册，无法充值\n请先注册此卡片",
                fg="#e74c3c"
            )
            self.card_uid = card_uid
            self.uid_label.config(text=card_uid[:12] + "..." if len(card_uid) > 12 else card_uid)
            self.identity_label.config(text="未注册")
            self.balance_label.config(text="0.00 元")

            # 禁用充值相关控件
            self.amount_entry.config(state="disabled")
            self.recharge_button.config(state="disabled", text="❌ 卡片未注册")
            for btn in self.quick_buttons:
                btn.config(state="disabled")

            # 设置2秒后恢复等待状态
            self.after(2000, self.reset_card_status)
        else:
            # 卡片已注册
            identity, balance = card_info

            self.card_uid = card_uid
            self.current_balance = balance
            self.card_identity = identity

            # 更新显示
            self.card_info_label.config(
                text=f"✓ 检测到{identity}卡\n当前余额: {balance:.2f}元",
                fg="#27ae60"
            )
            self.uid_label.config(text=card_uid[:12] + "..." if len(card_uid) > 12 else card_uid)
            self.identity_label.config(text=identity)
            self.balance_label.config(text=f"{balance:.2f} 元")

            # 启用充值相关控件
            self.amount_entry.config(state="normal")
            self.recharge_button.config(state="normal", text="✅ 确认充值")
            for btn in self.quick_buttons:
                btn.config(state="normal")

            self.waiting_for_card = False

    def reset_card_status(self):
        """重置卡片状态，准备读取下一张卡"""
        if not self.winfo_exists():
            return

        self.card_info_label.config(
            text="请将卡片靠近读卡器...",
            fg="#7f8c8d"
        )
        self.uid_label.config(text="未读取")
        self.identity_label.config(text="未知")
        self.balance_label.config(text="0.00 元")
        self.amount_entry.config(state="disabled")
        self.recharge_button.config(state="disabled", text="✅ 确认充值")
        for btn in self.quick_buttons:
            btn.config(state="disabled")

        self.card_uid = None
        self.current_balance = 0.0
        self.card_identity = "未知"
        self.waiting_for_card = True

    def _do_recharge(self):
        """执行充值"""
        if not self.card_uid:
            messagebox.showerror("错误", "请先刷卡！", parent=self)
            return

        try:
            amount = float(self.amount_var.get())
            if amount <= 0:
                messagebox.showerror("错误", "充值金额必须大于0！", parent=self)
                return
        except ValueError:
            messagebox.showerror("错误", "请输入有效的金额！", parent=self)
            return

        # 执行充值
        if self.db_manager.update_balance(self.card_uid, amount):
            new_balance = self.current_balance + amount
            self.db_manager.add_transaction_record(self.card_uid, '充值', amount, '成功')

            messagebox.showinfo("成功",
                                f"充值成功！\n"
                                f"卡片UID: {self.card_uid}\n"
                                f"充值金额: {amount}元\n"
                                f"新余额: {new_balance:.2f}元",
                                parent=self)

            # 执行回调（如果有）
            if self.on_recharged:
                self.on_recharged(self.card_uid, amount, new_balance)

            # 充值成功后重置状态
            self.reset_card_status()

            # 播放提示音
            self.beep_success()
        else:
            messagebox.showerror("失败", "充值失败！", parent=self)

    def beep_success(self):
        """播放成功提示音"""
        try:
            import winsound
            winsound.Beep(800, 200)
        except:
            try:
                print('\a')
            except:
                pass

    def destroy(self):
        """销毁窗口"""
        # 重置等待标志
        self.waiting_for_card = False
        super().destroy()


# ==================== 交易记录查询窗口 ====================
class TransactionWindow(tk.Toplevel):
    """交易记录查询窗口"""

    def __init__(self, parent, db_manager: DatabaseManager, card_uid: str = None):
        super().__init__(parent)
        self.parent = parent
        self.db_manager = db_manager
        self.card_uid = card_uid

        self.title("交易记录查询")
        self.geometry("900x600")
        self.configure(bg="#f0f0f0")

        self.setup_widgets()
        self.load_records()

    def setup_widgets(self):
        """设置控件"""
        # 主容器
        main_frame = tk.Frame(self, bg="#f0f0f0")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 标题
        tk.Label(main_frame, text="📊 交易记录查询", font=("微软雅黑", 18, "bold"),
                 bg="#f0f0f0", fg="#2c3e50").pack(pady=(0, 20))

        # 筛选条件
        filter_frame = tk.Frame(main_frame, bg="#ecf0f1", bd=1, relief="solid", padx=15, pady=15)
        filter_frame.pack(fill=tk.X, pady=(0, 20))

        # UID筛选
        tk.Label(filter_frame, text="卡片UID:", font=("微软雅黑", 10),
                 bg="#ecf0f1", width=10).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.uid_var = tk.StringVar()
        if self.card_uid:
            self.uid_var.set(self.card_uid)
        tk.Entry(filter_frame, textvariable=self.uid_var, width=25,
                 font=("微软雅黑", 10), bd=1, relief="solid").grid(row=0, column=1, padx=5, pady=5)

        # 时间筛选
        tk.Label(filter_frame, text="开始日期:", font=("微软雅黑", 10),
                 bg="#ecf0f1", width=10).grid(row=0, column=2, padx=(20, 5), pady=5)
        self.start_date_var = tk.StringVar(value="")
        tk.Entry(filter_frame, textvariable=self.start_date_var, width=12,
                 font=("微软雅黑", 10), bd=1, relief="solid").grid(row=0, column=3, padx=5, pady=5)

        tk.Label(filter_frame, text="结束日期:", font=("微软雅黑", 10),
                 bg="#ecf0f1", width=10).grid(row=0, column=4, padx=(20, 5), pady=5)
        self.end_date_var = tk.StringVar(value="")
        tk.Entry(filter_frame, textvariable=self.end_date_var, width=12,
                 font=("微软雅黑", 10), bd=1, relief="solid").grid(row=0, column=5, padx=5, pady=5)

        # 查询按钮
        tk.Button(filter_frame, text="🔍 查询", font=("微软雅黑", 10), bg="#3498db", fg="white",
                  padx=15, pady=5, bd=0, command=self.load_records).grid(row=0, column=6, padx=15, pady=5)

        # 交易记录表格
        tree_frame = tk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("ID", "卡片UID", "交易类型", "金额(元)", "交易时间", "状态")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=20)

        # 设置样式
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", font=("微软雅黑", 9), rowheight=25)
        style.configure("Treeview.Heading", font=("微软雅黑", 10, "bold"), background="#3498db",
                        foreground="white")
        style.map("Treeview.Heading", background=[("active", "#2980b9")])

        # 设置列宽
        column_widths = [50, 150, 100, 100, 180, 80]
        for col, width in zip(columns, column_widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, anchor=tk.CENTER)

        # 滚动条
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 按钮
        button_frame = tk.Frame(main_frame, bg="#f0f0f0")
        button_frame.pack(fill=tk.X, pady=15)

        tk.Button(
            button_frame, text="📤 导出CSV", font=("微软雅黑", 10), bg="#9b59b6", fg="white",
            padx=15, pady=5, bd=0, command=self.export_csv
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            button_frame, text="🔄 刷新", font=("微软雅黑", 10), bg="#3498db", fg="white",
            padx=15, pady=5, bd=0, command=self.load_records
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            button_frame, text="关闭", font=("微软雅黑", 10), bg="#95a5a6", fg="white",
            padx=15, pady=5, bd=0, command=self.destroy
        ).pack(side=tk.RIGHT, padx=5)

    def load_records(self):
        """加载交易记录"""
        # 清空现有数据
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 获取筛选条件
        uid = self.uid_var.get().strip() or None
        start_date = self.start_date_var.get().strip() or None
        end_date = self.end_date_var.get().strip() or None

        # 查询记录
        records = self.db_manager.query_transaction_records(uid, start_date, end_date)

        # 插入数据
        for record in records:
            # 格式化金额显示
            amount = float(record[3])
            amount_str = f"{amount:+.2f}"

            # 根据交易类型设置标签
            tags = ()
            if amount > 0:
                tags = ("充值",)
            elif amount < 0:
                tags = ("扣费",)
            else:
                tags = ("免费",)

            self.tree.insert("", tk.END, values=(
                record[0],  # ID
                record[1],  # UID
                record[2],  # 交易类型
                amount_str,  # 金额
                record[4],  # 时间
                record[5]  # 状态
            ), tags=tags)

        # 配置标签颜色
        self.tree.tag_configure("充值", foreground="#27ae60")
        self.tree.tag_configure("扣费", foreground="#e74c3c")
        self.tree.tag_configure("免费", foreground="#f39c12")

    def export_csv(self):
        """导出为CSV文件"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )

        if not filename:
            return

        try:
            # 获取筛选条件
            uid = self.uid_var.get().strip() or None
            start_date = self.start_date_var.get().strip() or None
            end_date = self.end_date_var.get().strip() or None

            # 查询记录
            records = self.db_manager.query_transaction_records(uid, start_date, end_date)

            # 写入CSV
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['ID', '卡片UID', '交易类型', '金额(元)', '交易时间', '状态'])

                for record in records:
                    writer.writerow(record)

            messagebox.showinfo("成功", f"数据已导出到: {filename}")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {str(e)}")


# ==================== 主界面 ====================
class BusCardUI:
    """公交车刷卡计费系统主界面"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("公交车刷卡计费系统 v1.0")
        self.root.geometry("1000x700")
        self.root.configure(bg="#2c3e50")

        # 数据库管理器
        self.db_manager = DatabaseManager()

        # 消息队列
        self.message_queue = queue.Queue()

        # RFID读取线程
        self.rfid_thread: Optional[RFIDReaderThread] = None

        # 窗口管理
        self.reg_window: Optional[RegistrationWindow] = None
        self.recharge_window: Optional[RechargeWindow] = None
        self.transaction_window: Optional[TransactionWindow] = None

        # 当前卡片信息（不再需要保存余额）
        self.current_card_uid = ""

        # 初始化UI
        self.setup_ui()

        # 启动消息处理
        self.process_messages()

        # 启动RFID线程
        self.start_rfid_thread()

    def setup_ui(self):
        """设置UI界面"""
        # 设置字体
        self.title_font = ("微软雅黑", 24, "bold")
        self.heading_font = ("微软雅黑", 14, "bold")
        self.normal_font = ("微软雅黑", 11)
        self.small_font = ("微软雅黑", 10)

        # 顶部标题栏
        self.create_title_bar()

        # 主容器
        main_container = tk.Frame(self.root, bg="#ecf0f1")
        main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # 左侧卡片信息面板
        self.create_card_info_panel(main_container)

        # 右侧控制面板
        self.create_control_panel(main_container)

        # 状态栏
        self.create_status_bar()

    def create_title_bar(self):
        """创建标题栏"""
        title_frame = tk.Frame(self.root, bg="#2c3e50", height=100)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)

        # 标题
        title_label = tk.Label(
            title_frame,
            text="🚌 公交车刷卡计费系统",
            font=self.title_font,
            fg="white",
            bg="#2c3e50"
        )
        title_label.pack(pady=20)

        # 副标题
        subtitle_label = tk.Label(
            title_frame,
            text="智能RFID刷卡扣费系统",
            font=("微软雅黑", 12),
            fg="#bdc3c7",
            bg="#2c3e50"
        )
        subtitle_label.pack(pady=(0, 20))

    def create_card_info_panel(self, parent):
        """创建卡片信息面板"""
        info_frame = tk.Frame(parent, bg="white", bd=2, relief="solid")
        info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 15))

        # 标题
        title_label = tk.Label(
            info_frame,
            text="📱 当前卡片信息",
            font=self.heading_font,
            bg="#3498db",
            fg="white",
            padx=20,
            pady=10
        )
        title_label.pack(fill=tk.X)

        # 信息内容容器
        content_frame = tk.Frame(info_frame, bg="white", padx=30, pady=30)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # 卡片状态指示器
        self.status_indicator = tk.Frame(content_frame, width=500, height=200, bg="#ecf0f1", bd=1, relief="solid")
        self.status_indicator.pack(pady=(0, 30))
        self.status_indicator.pack_propagate(False)

        # 状态文本
        self.status_label = tk.Label(
            self.status_indicator,
            text="等待刷卡...",
            font=("微软雅黑", 16),
            bg="#ecf0f1",
            fg="#7f8c8d"
        )
        self.status_label.place(relx=0.5, rely=0.4, anchor=tk.CENTER)

        # UID显示
        self.card_uid_label = tk.Label(
            self.status_indicator,
            text="未检测到卡片",
            font=("Consolas", 12),
            bg="#ecf0f1",
            fg="#7f8c8d"
        )
        self.card_uid_label.place(relx=0.5, rely=0.6, anchor=tk.CENTER)

        # 详细信息
        detail_frame = tk.Frame(content_frame, bg="white")
        detail_frame.pack(fill=tk.X)

        # 身份信息
        identity_frame = tk.Frame(detail_frame, bg="white")
        identity_frame.pack(fill=tk.X, pady=10)

        tk.Label(identity_frame, text="身份类型:", font=self.normal_font,
                 bg="white", width=10, anchor="w").pack(side=tk.LEFT)
        self.card_identity_label = tk.Label(identity_frame, text="未知",
                                            font=self.normal_font, bg="white", fg="#e67e22")
        self.card_identity_label.pack(side=tk.LEFT)

        # 注意：这里移除了余额信息的显示部分
        # 移除了以下代码：
        # 余额信息
        # balance_frame = tk.Frame(detail_frame, bg="white")
        # balance_frame.pack(fill=tk.X, pady=10)
        # tk.Label(balance_frame, text="当前余额:", font=self.normal_font,
        #          bg="white", width=10, anchor="w").pack(side=tk.LEFT)
        # self.card_balance_label = tk.Label(balance_frame, text="0.00 元",
        #                                    font=("微软雅黑", 18, "bold"), bg="white", fg="#27ae60")
        # self.card_balance_label.pack(side=tk.LEFT)

        # 最近交易记录（向上移动以填补余额移除后的空间）
        trans_frame = tk.LabelFrame(content_frame, text="最近交易记录",
                                    font=self.heading_font, bg="white", bd=1, relief="solid")
        trans_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))  # 减少上边距

        self.recent_trans_text = tk.Text(trans_frame, height=10, font=("Consolas", 10),  # 增加高度
                                         bg="#f8f9fa", bd=0, padx=10, pady=10)
        self.recent_trans_text.pack(fill=tk.BOTH, expand=True)

    def create_control_panel(self, parent):
        """创建控制面板"""
        control_frame = tk.Frame(parent, bg="white", bd=2, relief="solid", width=300)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y)
        control_frame.pack_propagate(False)

        # 标题
        title_label = tk.Label(
            control_frame,
            text="⚙️ 系统控制",
            font=self.heading_font,
            bg="#2c3e50",
            fg="white",
            padx=20,
            pady=10
        )
        title_label.pack(fill=tk.X)

        # 内容容器
        content_frame = tk.Frame(control_frame, bg="white", padx=20, pady=20)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # 连接状态
        status_frame = tk.Frame(content_frame, bg="white")
        status_frame.pack(fill=tk.X, pady=(0, 20))

        self.connection_label = tk.Label(
            status_frame,
            text="🔴 未连接",
            font=self.normal_font,
            bg="white",
            fg="#e74c3c"
        )
        self.connection_label.pack()

        # 统计信息
        stats_frame = tk.LabelFrame(content_frame, text="系统统计",
                                    font=self.heading_font, bg="white", bd=1, relief="solid")
        stats_frame.pack(fill=tk.X, pady=(0, 20))

        self.stats_label = tk.Label(
            stats_frame,
            text="已注册卡片: 0张\n总交易次数: 0次",
            font=self.normal_font,
            bg="white",
            justify=tk.LEFT,
            padx=15,
            pady=15
        )
        self.stats_label.pack()

        # 控制按钮 - 充值按钮始终可用
        button_configs = [
            ("💰 卡片充值", "#f39c12", self.open_recharge, "normal"),
            ("📊 交易记录", "#9b59b6", self.open_transaction, "normal"),
            ("🗑️ 清除数据", "#e74c3c", self.clear_data_confirm, "normal"),
            ("❌ 退出系统", "#34495e", self.quit_application, "normal")
        ]

        for text, color, command, state in button_configs:
            btn = tk.Button(
                content_frame,
                text=text,
                font=self.normal_font,
                bg=color,
                fg="white",
                width=20,
                height=2,
                command=command,
                state=state,
                bd=0,
                relief="flat",
                cursor="hand2"
            )
            btn.pack(pady=8)

    def create_status_bar(self):
        """创建状态栏"""
        status_bar = tk.Frame(self.root, bg="#34495e", height=40)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        status_bar.pack_propagate(False)

        # 左侧状态
        self.status_left = tk.Label(
            status_bar,
            text="就绪 | 模式: 自动读卡",
            bg="#34495e",
            fg="#ecf0f1",
            font=self.small_font
        )
        self.status_left.pack(side=tk.LEFT, padx=15)

        # 中间状态
        self.status_center = tk.Label(
            status_bar,
            text="RFID: 未连接",
            bg="#34495e",
            fg="#ecf0f1",
            font=self.small_font
        )
        self.status_center.pack(side=tk.LEFT, padx=15)

        # 右侧状态
        self.status_right = tk.Label(
            status_bar,
            text=f"数据库: {DB_FILE}",
            bg="#34495e",
            fg="#ecf0f1",
            font=self.small_font
        )
        self.status_right.pack(side=tk.RIGHT, padx=15)

    def start_rfid_thread(self):
        """启动RFID线程"""
        self.rfid_thread = RFIDReaderThread(
            self.db_manager,
            self.message_queue,
            IP,
            PORT
        )
        self.rfid_thread.daemon = True
        self.rfid_thread.start()

    def process_messages(self):
        """处理消息队列"""
        try:
            while True:
                try:
                    msg_type, data = self.message_queue.get_nowait()

                    if msg_type == "info":
                        self.connection_label.config(text="🟢 " + data, fg="green")
                        self.status_center.config(text=f"RFID: 已连接 ({IP})")
                        self.update_status_indicator("已连接", "#27ae60")
                    elif msg_type == "error":
                        self.connection_label.config(text="🔴 " + data, fg="red")
                        self.status_center.config(text="RFID: 连接失败")
                        self.update_status_indicator("连接失败", "#e74c3c")
                    elif msg_type == "register_request":
                        # 如果有充值窗口打开，转发消息到充值窗口
                        if self.recharge_window and self.recharge_window.winfo_exists():
                            self.recharge_window.handle_card_read(data)
                        else:
                            # 否则正常处理注册请求
                            self.handle_register_request(data)
                    elif msg_type == "deduct_success":
                        # 如果有充值窗口打开，转发消息到充值窗口
                        if self.recharge_window and self.recharge_window.winfo_exists():
                            self.recharge_window.handle_card_read(data['uid'])
                        else:
                            # 否则正常处理扣费成功
                            self.handle_deduct_success(data)
                    elif msg_type == "deduct_failed":
                        # 如果有充值窗口打开，转发消息到充值窗口
                        if self.recharge_window and self.recharge_window.winfo_exists():
                            self.recharge_window.handle_card_read(data['uid'])
                        else:
                            # 否则正常处理扣费失败
                            self.handle_deduct_failed(data)

                except queue.Empty:
                    break
        finally:
            self.root.after(100, self.process_messages)

    def update_status_indicator(self, text: str, color: str):
        """更新状态指示器"""
        self.status_label.config(text=text, fg=color)
        self.status_indicator.config(bg="#ecf0f1")

    def handle_register_request(self, card_uid: str):
        """处理注册请求"""
        # 检查是否已有注册窗口
        if self.reg_window and self.reg_window.winfo_exists():
            try:
                self.reg_window.lift()
                self.reg_window.focus_force()
            except:
                pass
            return

        # 更新状态指示器
        self.update_status_indicator("新卡片检测到", "#f39c12")
        self.card_uid_label.config(text=card_uid[:12] + "..." if len(card_uid) > 12 else card_uid)

        # 创建注册窗口
        self.reg_window = RegistrationWindow(
            self.root,
            self.db_manager,
            card_uid,
            on_registered=self.on_registration_complete
        )

    def on_registration_complete(self, card_uid: str, identity: str, balance: float):
        """注册完成回调"""
        # 更新当前卡片信息
        self.current_card_uid = card_uid

        # 更新UI显示（不再更新余额）
        self.card_uid_label.config(text=card_uid[:12] + "..." if len(card_uid) > 12 else card_uid, fg="#3498db")
        self.card_identity_label.config(text=identity)

        # 更新状态指示器
        self.update_status_indicator("注册成功", "#27ae60")
        self.status_label.config(text=f"{identity}卡注册成功")

        # 更新统计
        self.update_stats()

        # 播放提示音
        self.beep_success()

        # 清除注册窗口引用
        self.reg_window = None

    def handle_deduct_success(self, data: Dict):
        """处理扣费成功"""
        uid = data['uid']
        identity = data['identity']
        fee = data['fee']
        balance = data['balance']  # 虽然接收但不使用
        message = data['message']

        # 如果扣费的是当前显示的卡片
        if uid == self.current_card_uid:
            # 只更新UID和身份，不更新余额
            pass

        # 更新状态指示器
        self.update_status_indicator("扣费成功", "#27ae60")
        self.status_label.config(text=message)
        self.card_uid_label.config(text=uid[:12] + "..." if len(uid) > 12 else uid, fg="#3498db")
        self.card_identity_label.config(text=identity)

        # 更新最近交易记录
        self.update_recent_transactions(uid)

        # 更新统计
        self.update_stats()

        # 播放提示音
        self.beep_success()

    def handle_deduct_failed(self, data: Dict):
        """处理扣费失败"""
        uid = data['uid']
        identity = data['identity']
        fee = data['fee']
        balance = data['balance']  # 虽然接收但不使用
        message = data['message']

        # 更新状态指示器
        self.update_status_indicator("扣费失败", "#e74c3c")
        self.status_label.config(text=message)
        self.card_uid_label.config(text=uid[:12] + "..." if len(uid) > 12 else uid, fg="#e74c3c")
        self.card_identity_label.config(text=identity)

        # 播放错误提示音
        self.beep_error()

    def open_recharge(self):
        """打开充值窗口"""
        # 检查是否已有充值窗口
        if self.recharge_window and self.recharge_window.winfo_exists():
            try:
                self.recharge_window.lift()
                self.recharge_window.focus_force()
            except:
                pass
            return

        # 创建充值窗口
        self.recharge_window = RechargeWindow(
            self.root,
            self.db_manager,
            on_recharged=self.on_recharge_complete
        )

    def on_recharge_complete(self, card_uid: str, amount: float, new_balance: float):
        """充值完成回调"""
        # 如果充值的是当前显示的卡片，不更新余额显示
        if card_uid == self.current_card_uid:
            # 只更新状态指示器，不更新余额显示
            pass

        # 更新状态指示器
        self.update_status_indicator("充值成功", "#27ae60")
        self.status_label.config(text=f"充值成功: +{amount:.2f}元")

        # 更新最近交易记录
        self.update_recent_transactions(card_uid)

        # 更新统计
        self.update_stats()

        # 播放提示音
        self.beep_success()

        # 清除充值窗口引用
        self.recharge_window = None

    def open_transaction(self):
        """打开交易记录窗口"""
        # 检查是否已有交易记录窗口
        if self.transaction_window and self.transaction_window.winfo_exists():
            try:
                self.transaction_window.lift()
                self.transaction_window.focus_force()
            except:
                pass
            return

        # 创建交易记录窗口
        self.transaction_window = TransactionWindow(
            self.root,
            self.db_manager,
            self.current_card_uid
        )

    def update_recent_transactions(self, card_uid: str):
        """更新最近交易记录"""
        # 清空现有内容
        self.recent_trans_text.delete(1.0, tk.END)

        # 查询最近交易记录
        records = self.db_manager.query_transaction_records(card_uid, None, None)

        if records:
            for record in records[:8]:  # 显示最近8条记录（因为空间变大了）
                trans_time = record[4]
                trans_type = record[2]
                amount = float(record[3])
                status = record[5]

                # 格式化显示
                amount_str = f"{amount:+.2f}"
                color = "#27ae60" if amount > 0 else "#e74c3c" if amount < 0 else "#f39c12"

                self.recent_trans_text.insert(tk.END,
                                              f"{trans_time}\n{trans_type}: ", "normal")
                self.recent_trans_text.insert(tk.END,
                                              f"{amount_str}元", ("colored",))
                self.recent_trans_text.insert(tk.END,
                                              f" ({status})\n\n", "normal")

                # 配置标签颜色
                self.recent_trans_text.tag_config("colored", foreground=color)
        else:
            self.recent_trans_text.insert(tk.END, "暂无交易记录\n")

    def update_stats(self):
        """更新统计信息"""
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM card_info")
            total_cards = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM transaction_record")
            total_transactions = cursor.fetchone()[0]

            conn.close()

            self.stats_label.config(
                text=f"已注册卡片: {total_cards}张\n总交易次数: {total_transactions}次"
            )
        except Exception as e:
            print(f"更新统计失败: {e}")

    def clear_data_confirm(self):
        """确认清除数据"""
        if messagebox.askyesno("确认", "确定要清除所有数据吗？\n此操作将删除所有卡片和交易记录，且不可恢复！"):
            self.clear_data()

    def clear_data(self):
        """清除数据"""
        try:
            success = self.db_manager.clear_all_data()
            if success:
                # 清空UI显示
                self.current_card_uid = ""

                self.card_uid_label.config(text="未检测到卡片", fg="#7f8c8d")
                self.card_identity_label.config(text="未知")
                self.recent_trans_text.delete(1.0, tk.END)

                self.update_status_indicator("等待刷卡...", "#7f8c8d")

                self.update_stats()
                messagebox.showinfo("成功", "所有数据已清除")
            else:
                messagebox.showerror("错误", "清除数据失败")
        except Exception as e:
            messagebox.showerror("错误", f"清除数据失败: {str(e)}")

    def beep_success(self):
        """播放成功提示音"""
        try:
            import winsound
            winsound.Beep(800, 200)
        except:
            try:
                print('\a')
            except:
                pass

    def beep_error(self):
        """播放错误提示音"""
        try:
            import winsound
            winsound.Beep(400, 300)
            time.sleep(0.1)
            winsound.Beep(400, 300)
        except:
            try:
                print('\a\a')
            except:
                pass

    def quit_application(self):
        """退出应用程序"""
        if messagebox.askyesno("确认", "确定要退出系统吗？"):
            # 关闭所有子窗口
            for child in self.root.winfo_children():
                if isinstance(child, tk.Toplevel):
                    try:
                        child.destroy()
                    except:
                        pass

            # 停止RFID线程
            if self.rfid_thread:
                self.rfid_thread.stop()
                self.rfid_thread.join(timeout=1)

            self.root.quit()

    def run(self):
        """运行应用程序"""
        # 初始加载数据
        self.update_stats()

        # 启动主循环
        self.root.mainloop()


# ==================== 主程序入口 ====================
if __name__ == "__main__":
    print("=" * 60)
    print("公交车刷卡计费系统 v1.0")
    print("=" * 60)
    print(f"数据库文件: {DB_FILE}")
    print(f"RFID设备: {IP}:{PORT}")
    print("正在启动系统...")

    try:
        app = BusCardUI()
        app.run()
    except Exception as e:
        print(f"启动失败: {e}")
        import traceback

        traceback.print_exc()
        input("按Enter键退出...")