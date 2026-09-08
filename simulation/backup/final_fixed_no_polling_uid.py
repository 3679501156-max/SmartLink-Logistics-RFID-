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
IP = '192.168.0.160'  # 使用实际IP，可在设置中修改
PORT = 4001
DB_FILE = "orienteering.db"

# ==================== RFID通信模块 ====================
class RFIDWiFiReader:
    """RFID读卡器通信类（基于老师代码优化）"""
    
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
        """被动接收一帧响应数据（不发送指令，用于上位机已下发指令的场景）"""
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
    
    def read_card_uid(self, antenna_no: int) -> Optional[str]:
        """读取指定天线的卡片UID（完整流程）"""
        if not self.select_antenna(antenna_no):
            return None
        
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
    """数据库管理类"""
    
    def __init__(self, db_file: str = DB_FILE):
        self.db_file = db_file
        self.init_database()
    
    def init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # 创建参赛者表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_uid TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                gender TEXT,
                age INTEGER,
                team TEXT,
                phone TEXT,
                emergency_contact TEXT,
                registration_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        ''')
        
        # 创建检查点表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                antenna_no INTEGER UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                sequence INTEGER,
                points INTEGER DEFAULT 10,
                location TEXT
            )
        ''')
        
        # 创建打卡记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS punch_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                participant_id INTEGER NOT NULL,
                checkpoint_id INTEGER NOT NULL,
                antenna_no INTEGER NOT NULL,
                punch_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                valid BOOLEAN DEFAULT 1,
                FOREIGN KEY (participant_id) REFERENCES participants(id),
                FOREIGN KEY (checkpoint_id) REFERENCES checkpoints(id)
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_card_uid ON participants(card_uid)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_punch_time ON punch_records(punch_time)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_participant_checkpoint ON punch_records(participant_id, checkpoint_id)')
        
        # 初始化检查点
        self._init_checkpoints(cursor)
        
        conn.commit()
        conn.close()
    
    def _init_checkpoints(self, cursor):
        """初始化检查点数据"""
        checkpoints = [
            (1, "起点/注册点", "比赛起点，用于注册选手", 0, 0, "起点区域"),
            (2, "检查点A", "第一个检查点", 1, 10, "A区"),
            (3, "检查点B", "第二个检查点", 2, 10, "B区"),
            (4, "检查点C", "第三个检查点", 3, 10, "C区"),
            (5, "检查点D", "第四个检查点", 4, 10, "D区"),
            (6, "检查点E", "第五个检查点", 5, 10, "E区"),
            (7, "检查点F", "第六个检查点", 6, 10, "F区"),
            (8, "终点", "比赛终点", 7, 20, "终点区域")
        ]
        
        for cp in checkpoints:
            cursor.execute('''
                INSERT OR IGNORE INTO checkpoints (antenna_no, name, description, sequence, points, location)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', cp)
    
    def register_participant(self, card_uid: str, name: str, gender: str = "", 
                           age: int = 0, team: str = "", phone: str = "", 
                           emergency_contact: str = "") -> Tuple[bool, str, Optional[int]]:
        """注册参赛者"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO participants (card_uid, name, gender, age, team, phone, emergency_contact)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (card_uid, name, gender, age, team, phone, emergency_contact))
            
            conn.commit()
            participant_id = cursor.lastrowid
            return True, f"选手 {name} 注册成功！", participant_id
        except sqlite3.IntegrityError:
            return False, f"卡号 {card_uid} 已注册！", None
        except Exception as e:
            return False, f"注册失败: {str(e)}", None
        finally:
            conn.close()
    
    def get_participant_by_card(self, card_uid: str) -> Optional[Dict]:
        """根据卡号获取参赛者信息"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, team, phone FROM participants WHERE card_uid = ?
        ''', (card_uid,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'name': row[1],
                'team': row[2],
                'phone': row[3]
            }
        return None
    
    def record_punch(self, participant_id: int, antenna_no: int, 
                     punch_time: Optional[str] = None) -> Tuple[bool, str]:
        """记录打卡"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        try:
            # 获取检查点ID
            cursor.execute("SELECT id FROM checkpoints WHERE antenna_no = ?", (antenna_no,))
            checkpoint = cursor.fetchone()
            
            if not checkpoint:
                return False, "无效的检查点"
            
            checkpoint_id = checkpoint[0]
            
            # 检查是否已在该检查点打卡（5分钟内不重复记录）
            cursor.execute('''
                SELECT id FROM punch_records 
                WHERE participant_id = ? AND checkpoint_id = ? 
                AND punch_time >= datetime('now', '-5 minutes')
            ''', (participant_id, checkpoint_id))
            
            if cursor.fetchone():
                return False, "该检查点最近已打卡"
            
            # 插入打卡记录
            if punch_time:
                cursor.execute('''
                    INSERT INTO punch_records (participant_id, checkpoint_id, antenna_no, punch_time)
                    VALUES (?, ?, ?, ?)
                ''', (participant_id, checkpoint_id, antenna_no, punch_time))
            else:
                cursor.execute('''
                    INSERT INTO punch_records (participant_id, checkpoint_id, antenna_no)
                    VALUES (?, ?, ?)
                ''', (participant_id, checkpoint_id, antenna_no))
            
            conn.commit()
            return True, "打卡成功"
        except Exception as e:
            return False, f"打卡失败: {str(e)}"
        finally:
            conn.close()
    
    def get_participant_progress(self, participant_id: int) -> Dict:
        """获取参赛者进度"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # 获取参赛者基本信息
        cursor.execute('SELECT name, team FROM participants WHERE id = ?', (participant_id,))
        participant = cursor.fetchone()
        
        if not participant:
            conn.close()
            return {'name': '未知', 'records': []}
        
        name, team = participant
        
        # 获取打卡记录
        cursor.execute('''
            SELECT c.name, c.antenna_no, pr.punch_time, c.sequence
            FROM punch_records pr
            JOIN checkpoints c ON pr.checkpoint_id = c.id
            WHERE pr.participant_id = ?
            ORDER BY pr.punch_time
        ''', (participant_id,))
        
        records = cursor.fetchall()
        
        # 获取所有检查点
        cursor.execute('SELECT name, sequence FROM checkpoints ORDER BY sequence')
        all_checkpoints = cursor.fetchall()
        
        conn.close()
        
        # 计算进度
        completed_checkpoints = [record[0] for record in records]
        total_checkpoints = len(all_checkpoints)
        completed_count = len(completed_checkpoints)
        
        progress = (completed_count / total_checkpoints * 100) if total_checkpoints > 0 else 0
        
        return {
            'name': name,
            'team': team,
            'records': records,
            'completed_checkpoints': completed_checkpoints,
            'completed_count': completed_count,
            'total_checkpoints': total_checkpoints,
            'progress': progress
        }
    
    def get_all_participants_summary(self) -> List[Dict]:
        """获取所有参赛者摘要信息"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                p.id,
                p.name,
                p.team,
                p.card_uid,
                COUNT(DISTINCT pr.checkpoint_id) as checkpoints_visited,
                MIN(pr.punch_time) as first_punch,
                MAX(pr.punch_time) as last_punch
            FROM participants p
            LEFT JOIN punch_records pr ON p.id = pr.participant_id
            GROUP BY p.id
            ORDER BY checkpoints_visited DESC, last_punch ASC
        ''')
        
        participants = cursor.fetchall()
        conn.close()
        
        result = []
        for p in participants:
            result.append({
                'id': p[0],
                'name': p[1],
                'team': p[2],
                'card_uid': p[3],
                'checkpoints_visited': p[4] or 0,
                'first_punch': p[5] or "未打卡",
                'last_punch': p[6] or "未打卡"
            })
        
        return result
    
    def get_detailed_results(self) -> List[Dict]:
        """获取详细结果"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                p.name,
                p.team,
                p.card_uid,
                GROUP_CONCAT(c.name || '@' || strftime('%H:%M:%S', pr.punch_time), ' -> ') as punch_sequence
            FROM participants p
            LEFT JOIN punch_records pr ON p.id = pr.participant_id
            LEFT JOIN checkpoints c ON pr.checkpoint_id = c.id
            GROUP BY p.id
            ORDER BY MAX(pr.punch_time) ASC
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        formatted_results = []
        for r in results:
            formatted_results.append({
                'name': r[0],
                'team': r[1],
                'card_uid': r[2],
                'punch_sequence': r[3] or "未打卡"
            })
        
        return formatted_results
    
    def clear_all_data(self):
        """清除所有数据"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM punch_records")
        cursor.execute("DELETE FROM participants")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('participants', 'punch_records')")
        
        conn.commit()
        conn.close()
    
    def export_to_csv(self, filename: str):
        """导出数据到CSV"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # 获取所有数据
        cursor.execute('''
            SELECT 
                p.name,
                p.team,
                p.card_uid,
                c.name as checkpoint,
                strftime('%Y-%m-%d %H:%M:%S', pr.punch_time) as punch_time
            FROM punch_records pr
            JOIN participants p ON pr.participant_id = p.id
            JOIN checkpoints c ON pr.checkpoint_id = c.id
            ORDER BY p.name, pr.punch_time
        ''')
        
        data = cursor.fetchall()
        conn.close()
        
        # 写入CSV
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['姓名', '队伍', '卡号', '检查点', '打卡时间'])
            writer.writerows(data)

# ==================== RFID读取线程 ====================
class RFIDReaderThread(threading.Thread):
    """RFID读取线程"""
    
    def __init__(self, db_manager: DatabaseManager, message_queue: queue.Queue,
                 ip: str = IP, port: int = PORT):
        super().__init__()
        self.db_manager = db_manager
        self.message_queue = message_queue
        self.ip = ip
        self.port = port
        self.running = True
        self.race_started = False
        self.current_mode = "register"  # register, race, or idle
        self.reader: Optional[RFIDWiFiReader] = None
        self.polling_interval = 1.0  # 轮询间隔
        self.last_read = {}  # 用于去重: {(card_uid, antenna): timestamp}
        
    def run(self):
        """线程主函数"""
        try:
            self.reader = RFIDWiFiReader(self.ip, self.port)
            if not self.reader.connect():
                self.message_queue.put(("error", "无法连接到RFID读卡器"))
                return
            
            self.message_queue.put(("info", "已连接到RFID读卡器"))
            
            while self.running:
                if self.current_mode == "register":
                    self._register_mode()
                elif self.current_mode == "race" and self.race_started:
                    self._race_mode()
                else:
                    time.sleep(0.5)
                    
        except Exception as e:
            self.message_queue.put(("error", f"线程错误: {str(e)}"))
        finally:
            if self.reader:
                self.reader.disconnect()
    
    def _register_mode(self):
        """注册模式：只在天线1检测"""
        card_uid = self._read_single_antenna(1)
        if card_uid:
            # 检查是否已注册
            participant = self.db_manager.get_participant_by_card(card_uid)
            if not participant:
                # 防抖检查：同一卡片10秒内不重复触发
                key = (card_uid, 1)
                current_time = time.time()
                
                if key in self.last_read and current_time - self.last_read[key] < 10:
                    return
                
                self.last_read[key] = current_time
                self.message_queue.put(("register_request", card_uid))
        time.sleep(0.5)
    
    def _race_mode(self):
        """比赛模式：不再轮询/发送指令，直接处理WiFi串口返回的UID"""
        if not self.reader or not self.reader.connected:
            time.sleep(0.5)
            return

        # 被动接收：另一个上位机已负责发送读卡指令，本程序只接收响应并解析UID
        raw = self.reader.recv_frame(timeout=0.5)
        if raw:
            parsed = self.reader.parse_response(raw)
            if parsed and parsed.get('status_code') == 0x00 and 'uid' in parsed:
                self._process_punch(parsed['uid'])
        time.sleep(0.05)

    def _read_single_antenna(self, antenna: int) -> Optional[str]:
        """读取单个天线的卡片UID"""
        try:
            if not self.reader or not self.reader.connected:
                return None
            
            return self.reader.read_card_uid(antenna)
            
        except Exception as e:
            print(f"读取天线{antenna}错误: {e}")
            return None
    
    def _process_punch(self, card_uid: str):
        """处理打卡（无天线号：按选手当前进度自动推进到下一个检查点）"""
        # 查找参赛者
        participant = self.db_manager.get_participant_by_card(card_uid)
        if not participant:
            return

        # 根据已完成的检查点数量，推算本次应记录的检查点（2~8）
        progress = self.db_manager.get_participant_progress(participant['id'])
        completed = int(progress.get('completed_count', 0))
        antenna = completed + 2
        if antenna > 8:
            antenna = 8

        # 去重检查：同一卡片在同一检查点30秒内不重复处理
        key = (card_uid, antenna)
        current_time = time.time()
        if key in self.last_read and current_time - self.last_read[key] < 30:
            return
        self.last_read[key] = current_time

        # 记录打卡
        success, message = self.db_manager.record_punch(participant['id'], antenna)

        if success:
            current_time_str = datetime.now().strftime("%H:%M:%S")
            self.message_queue.put(("punch", {
                'name': participant['name'],
                'antenna': antenna,
                'time': current_time_str,
                'card_uid': card_uid
            }))

            # 如果是终点，发送完成消息
            if antenna == 8:
                self.message_queue.put(("finish", {
                    'name': participant['name'],
                    'time': current_time_str
                }))

    def set_mode(self, mode: str):
        """设置工作模式"""
        if mode in ["register", "race", "idle"]:
            self.current_mode = mode
    
    def start_race(self):
        """开始比赛"""
        self.race_started = True
    
    def stop_race(self):
        """结束比赛"""
        self.race_started = False
    
    def stop(self):
        """停止线程"""
        self.running = False

# ==================== 注册窗口 ====================
class RegistrationWindow(tk.Toplevel):
    """注册新选手窗口（优化版）"""

    def __init__(self, parent, db_manager: DatabaseManager, card_uid: str, 
                 on_registered: callable, on_cancel: callable):
        super().__init__(parent)
        self.parent = parent
        self.db_manager = db_manager
        self.card_uid = card_uid
        self.on_registered = on_registered  # 注册成功回调
        self.on_cancel = on_cancel  # 取消回调
        self.is_closed = False  # 窗口状态标记

        self.title(f"注册新选手 - 卡号: {card_uid}")
        self.geometry("400x400")
        self.resizable(False, False)
        
        # 设置窗口始终在最前面
        self.transient(parent)
        self.grab_set()
        
        # 绑定窗口关闭事件
        self.protocol("WM_DELETE_WINDOW", self._on_window_close)
        
        # 设置超时自动关闭（60秒）
        self.timeout_id = self.after(60000, self._on_timeout)
        
        self.setup_widgets()
        
        # 自动聚焦到姓名输入框
        self.after(100, lambda: self.name_entry.focus_set())

    def setup_widgets(self):
        form_frame = tk.LabelFrame(self, text="选手信息", font=("微软雅黑", 12, "bold"))
        form_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        normal_font = ("微软雅黑", 10)

        fields = [
            ("卡号:", self.card_uid, True),
            ("姓名*:", "name_entry", False),
            ("性别:", "gender_var", False),
            ("年龄:", "age_entry", False),
            ("队伍:", "team_entry", False),
            ("电话:", "phone_entry", False),
            ("紧急联系人:", "emergency_contact_entry", False)
        ]

        for i, (label_text, var_name, readonly) in enumerate(fields):
            tk.Label(form_frame, text=label_text, font=normal_font).grid(
                row=i, column=0, sticky=tk.W, padx=10, pady=5
            )

            if readonly:
                tk.Label(form_frame, text=var_name, font=normal_font, fg="blue").grid(
                    row=i, column=1, sticky=tk.W, padx=10, pady=5
                )
            elif var_name == "gender_var":
                self.gender_var = tk.StringVar(value="男")
                frame = tk.Frame(form_frame)
                frame.grid(row=i, column=1, sticky=tk.W, padx=10, pady=5)
                tk.Radiobutton(frame, text="男", variable=self.gender_var, value="男").pack(side=tk.LEFT)
                tk.Radiobutton(frame, text="女", variable=self.gender_var, value="女").pack(side=tk.LEFT)
            else:
                entry = tk.Entry(form_frame, width=30, font=normal_font)
                entry.grid(row=i, column=1, sticky=tk.W, padx=10, pady=5)
                setattr(self, var_name, entry)

        # 提示信息
        tk.Label(form_frame, text="* 为必填项", font=("微软雅黑", 9), fg="red").grid(
            row=len(fields), column=0, columnspan=2, pady=5
        )

        # 按钮
        button_frame = tk.Frame(form_frame)
        button_frame.grid(row=len(fields)+1, column=0, columnspan=2, pady=20)

        tk.Button(
            button_frame, text="✅ 注册", font=normal_font, 
            bg="#27ae60", fg="white", width=10, command=self._do_register
        ).pack(side=tk.LEFT, padx=10)
        
        tk.Button(
            button_frame, text="⏭️ 跳过", font=normal_font, 
            bg="#f39c12", fg="white", width=10, command=self._skip
        ).pack(side=tk.LEFT, padx=10)
        
        tk.Button(
            button_frame, text="❌ 取消", font=normal_font, 
            bg="#e74c3c", fg="white", width=10, command=self._cancel
        ).pack(side=tk.LEFT, padx=10)

    def _do_register(self):
        """注册选手"""
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showerror("错误", "姓名不能为空！", parent=self)
            return

        age_str = self.age_entry.get().strip()
        try:
            age = int(age_str) if age_str else 0
        except ValueError:
            messagebox.showerror("错误", "年龄必须是数字！", parent=self)
            return

        team = self.team_entry.get().strip()
        phone = self.phone_entry.get().strip()
        emergency_contact = self.emergency_contact_entry.get().strip()

        success, message, participant_id = self.db_manager.register_participant(
            self.card_uid, name, self.gender_var.get(), age, team,
            phone, emergency_contact
        )

        if success:
            # 取消超时
            if self.timeout_id:
                self.after_cancel(self.timeout_id)
            
            self.is_closed = True
            messagebox.showinfo("成功", message, parent=self)
            self.destroy()
            
            # 回调主界面
            if self.on_registered:
                self.on_registered()
        else:
            messagebox.showerror("注册失败", message, parent=self)

    def _skip(self):
        """跳过此卡片"""
        if messagebox.askyesno("确认", "确定要跳过此卡片吗？\n此卡片将不会被注册。", parent=self):
            self._close_window()
            if self.on_cancel:
                self.on_cancel()

    def _cancel(self):
        """取消注册"""
        if messagebox.askyesno("确认", "确定要取消注册吗？", parent=self):
            self._close_window()
            if self.on_cancel:
                self.on_cancel()

    def _on_timeout(self):
        """超时自动关闭"""
        messagebox.showwarning("超时", "注册窗口已超时关闭。", parent=self)
        self._close_window()
        if self.on_cancel:
            self.on_cancel()

    def _on_window_close(self):
        """窗口关闭事件"""
        self._close_window()
        if self.on_cancel:
            self.on_cancel()

    def _close_window(self):
        """安全关闭窗口"""
        if not self.is_closed:
            self.is_closed = True
            # 取消超时定时器
            if self.timeout_id:
                self.after_cancel(self.timeout_id)
            self.destroy()

    def destroy(self):
        """重写destroy方法以确保资源释放"""
        if not self.is_closed:
            self.is_closed = True
            # 释放模态锁定
            try:
                self.grab_release()
            except:
                pass
        super().destroy()

# ==================== UI界面 ====================
class OrienteeringUI:
    """定向越野系统UI（优化版）"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("定向越野管理系统 v2.1")
        self.root.geometry("1000x750")
        
        # 数据库管理器
        self.db_manager = DatabaseManager()
        
        # 消息队列
        self.message_queue = queue.Queue()
        
        # RFID读取线程
        self.rfid_thread: Optional[RFIDReaderThread] = None
        
        # 比赛计时
        self.race_start_time: Optional[datetime] = None
        self.timer_job = None
        
        # 注册窗口管理
        self.reg_window: Optional[RegistrationWindow] = None
        self.last_registration_time = 0
        
        # 系统配置
        self.config = {
            'ip': IP,
            'port': PORT,
            'polling_interval': 0.3
        }
        
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
        self.heading_font = ("微软雅黑", 12, "bold")
        self.normal_font = ("微软雅黑", 10)
        
        # 顶部标题栏
        self.create_title_bar()
        
        # 主容器
        main_container = tk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧控制面板
        self.create_control_panel(main_container)
        
        # 右侧主面板
        self.create_main_panel(main_container)
        
        # 状态栏
        self.create_status_bar()
    
    def create_title_bar(self):
        """创建标题栏"""
        title_frame = tk.Frame(self.root, bg="#2c3e50", height=70)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        tk.Label(
            title_frame, 
            text="🏃 定向越野管理系统 v2.1", 
            font=self.title_font, 
            fg="white", 
            bg="#2c3e50"
        ).pack(pady=15)
    
    def create_control_panel(self, parent):
        """创建控制面板"""
        control_frame = tk.LabelFrame(parent, text="比赛控制", font=self.heading_font)
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        # 连接状态
        self.connection_label = tk.Label(
            control_frame, 
            text="🔴 未连接", 
            font=self.normal_font,
            fg="red"
        )
        self.connection_label.pack(pady=5)
        
        # 系统状态
        self.system_status_label = tk.Label(
            control_frame,
            text="状态: 等待开始",
            font=self.normal_font,
            fg="blue"
        )
        self.system_status_label.pack(pady=5)
        
        # 比赛时间
        self.time_label = tk.Label(
            control_frame,
            text="比赛时间: 00:00:00",
            font=self.normal_font,
            fg="green"
        )
        self.time_label.pack(pady=10)
        
        # 控制按钮
        button_configs = [
            ("🚩 开始比赛", "#27ae60", self.start_race, "normal"),
            ("🛑 结束比赛", "#e74c3c", self.end_race, "disabled"),
#            ("👤 手动注册", "#3498db", self.manual_register, "normal"),
            ("📊 查看成绩", "#9b59b6", self.show_results, "normal"),
            ("📈 实时排名", "#f39c12", self.show_live_ranking, "normal"),
            ("⚙️ 系统设置", "#7f8c8d", self.open_settings, "normal"),
            ("🗑️ 清除数据", "#e74c3c", self.clear_data_confirm, "normal"),
            ("📤 导出数据", "#2ecc71", self.export_data, "normal"),
            ("❌ 退出系统", "#34495e", self.quit_application, "normal")
        ]
        
        self.buttons = {}
        for text, color, command, state in button_configs:
            btn = tk.Button(
                control_frame,
                text=text,
                font=self.normal_font,
                bg=color,
                fg="white",
                width=15,
                height=1,
                command=command,
                state=state
            )
            btn.pack(pady=5)
            self.buttons[text] = btn
        
        # 统计信息
        stats_frame = tk.Frame(control_frame)
        stats_frame.pack(pady=10, fill=tk.X)
        
        self.stats_label = tk.Label(
            stats_frame,
            text="选手: 0人 | 打卡: 0次",
            font=self.normal_font
        )
        self.stats_label.pack()
        
        # 进度条
        self.progress_label = tk.Label(
            control_frame,
            text="注册进度: 0人",
            font=self.normal_font
        )
        self.progress_label.pack(pady=5)
        
        self.progress_bar = ttk.Progressbar(
            control_frame,
            length=150,
            mode='determinate'
        )
        self.progress_bar.pack(pady=5)
    
    def create_main_panel(self, parent):
        """创建主面板"""
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # 注册选项卡
        self.create_registration_tab(notebook)
        
        # 实时监控选项卡
        self.create_monitor_tab(notebook)
        
        # 选手管理选项卡
        self.create_participants_tab(notebook)
        
        # 系统日志选项卡
        self.create_log_tab(notebook)
    
    def create_registration_tab(self, notebook):
        """创建注册选项卡"""
        reg_frame = ttk.Frame(notebook)
        notebook.add(reg_frame, text="选手注册")
    
        # 手动注册表单 - 修改布局
        form_frame = tk.LabelFrame(reg_frame, text="手动注册", font=self.heading_font)
        form_frame.pack(fill=tk.X, padx=10, pady=10)
    
    # 重新组织字段，让它们都在同一列
        fields = [
            ("卡号:", "manual_card_entry", False),
            ("姓名:", "manual_name_entry", False),
            ("性别:", "manual_gender_var", False),
            ("年龄:", "manual_age_entry", False),
            ("队伍:", "manual_team_entry", False),
            ("电话:", "manual_phone_entry", False)
        ]
    
    # 使用统一的网格布局
        for i, (label_text, var_name, readonly) in enumerate(fields):
            # 标签
            tk.Label(form_frame, text=label_text, font=self.normal_font).grid(
                    row=i, column=0, sticky=tk.W, padx=(10, 5), pady=5
            )
        
            if var_name == "manual_gender_var":
                # 性别选择（单选按钮）
                var = tk.StringVar(value="男")
                frame = tk.Frame(form_frame)
                frame.grid(row=i, column=1, sticky=tk.W, padx=5, pady=5)
                tk.Radiobutton(frame, text="男", variable=var, value="男", 
                              font=self.normal_font).pack(side=tk.LEFT, padx=(0, 10))
                tk.Radiobutton(frame, text="女", variable=var, value="女",
                          font=self.normal_font).pack(side=tk.LEFT)
                setattr(self, var_name, var)
            else:
            # 输入框
                var = tk.Entry(form_frame, width=35, font=self.normal_font)
                var.grid(row=i, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
                setattr(self, var_name, var)
    
        # 让第二列可以扩展
        form_frame.grid_columnconfigure(1, weight=1)
    
        # 按钮框架 - 放在表单下方
        button_frame = tk.Frame(form_frame)
        button_frame.grid(row=len(fields), column=0, columnspan=2, pady=15)
    
        tk.Button(
            button_frame,
            text="✅ 注册选手",
            font=self.normal_font,
            bg="#27ae60",
            fg="white",
            padx=15,
            command=self.manual_register_submit
        ).pack(side=tk.LEFT, padx=10)
    
        tk.Button(
            button_frame,
            text="🔄 重置表单",
            font=self.normal_font,
            padx=15,
            command=self.reset_manual_form
        ).pack(side=tk.LEFT, padx=10)
    
        # 提示信息
        tk.Label(
            button_frame,
            text="* 卡号和姓名为必填项",
            font=("微软雅黑", 9),
            fg="red"
        ).pack(side=tk.LEFT, padx=20)
    
        # 已注册选手列表
        list_frame = tk.LabelFrame(reg_frame, text="已注册选手", font=self.heading_font)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
        columns = ("序号", "姓名", "队伍", "卡号", "注册时间")
        self.reg_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)
    
        for col in columns:
            self.reg_tree.heading(col, text=col)
            if col == "序号":
                self.reg_tree.column(col, width=60, anchor=tk.CENTER)
            elif col == "注册时间":
                self.reg_tree.column(col, width=120)
            else:
                self.reg_tree.column(col, width=100)
    
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.reg_tree.yview)
        self.reg_tree.configure(yscrollcommand=scrollbar.set)
    
        self.reg_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
        # 刷新按钮 - 放在列表下方
        refresh_frame = tk.Frame(list_frame)
        refresh_frame.pack(fill=tk.X, pady=(5, 0))
    
        tk.Button(
            refresh_frame,
            text="🔄 刷新列表",
            font=self.normal_font,
            command=self.refresh_participants_list
        ).pack(pady=5)



    
    def create_monitor_tab(self, notebook):
        """创建监控选项卡"""
        monitor_frame = ttk.Frame(notebook)
        notebook.add(monitor_frame, text="实时监控")
        
        # 打卡信息
        punch_frame = tk.LabelFrame(monitor_frame, text="实时打卡信息", font=self.heading_font)
        punch_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.punch_text = tk.Text(
            punch_frame,
            height=20,
            font=("Consolas", 10),
            bg="#f8f9fa"
        )
        self.punch_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 添加滚动条
        scrollbar = tk.Scrollbar(self.punch_text)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.punch_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.punch_text.yview)
        
        # 控制按钮
        control_frame = tk.Frame(punch_frame)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Button(
            control_frame,
            text="🗑️ 清空日志",
            font=self.normal_font,
            command=lambda: self.punch_text.delete(1.0, tk.END)
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            control_frame,
            text="💾 保存日志",
            font=self.normal_font,
            command=self.save_punch_log
        ).pack(side=tk.LEFT, padx=5)
        
        # 天线状态显示
        antenna_frame = tk.LabelFrame(monitor_frame, text="天线状态", font=self.heading_font)
        antenna_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.antenna_labels = {}
        for i in range(1, 9):
            frame = tk.Frame(antenna_frame)
            frame.pack(side=tk.LEFT, padx=5, pady=5)
            
            label = tk.Label(
                frame,
                text=f"天线{i}",
                font=self.normal_font,
                width=8,
                bg="#ecf0f1"
            )
            label.pack()
            
            status = tk.Label(
                frame,
                text="🔴",
                font=self.normal_font
            )
            status.pack()
            
            self.antenna_labels[i] = (label, status)
    
    def create_participants_tab(self, notebook):
        """创建选手管理选项卡"""
        part_frame = ttk.Frame(notebook)
        notebook.add(part_frame, text="选手管理")
        
        # 搜索框
        search_frame = tk.Frame(part_frame)
        search_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(search_frame, text="搜索:", font=self.normal_font).pack(side=tk.LEFT, padx=5)
        
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *args: self.search_participants())
        tk.Entry(search_frame, textvariable=self.search_var, width=30, font=self.normal_font).pack(side=tk.LEFT, padx=5)
        
        # 选手表格
        tree_frame = tk.Frame(part_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        columns = ("ID", "姓名", "队伍", "卡号", "年龄", "性别", "电话")
        self.part_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)
        
        for col in columns:
            self.part_tree.heading(col, text=col)
            self.part_tree.column(col, width=100)
        
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.part_tree.yview)
        self.part_tree.configure(yscrollcommand=scrollbar.set)
        
        self.part_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 操作按钮
        button_frame = tk.Frame(part_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Button(
            button_frame,
            text="🔄 刷新",
            font=self.normal_font,
            command=self.load_participants
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            button_frame,
            text="👁️ 查看详情",
            font=self.normal_font,
            command=self.view_participant_details
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            button_frame,
            text="✏️ 编辑",
            font=self.normal_font,
            command=self.edit_participant
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            button_frame,
            text="🗑️ 删除",
            font=self.normal_font,
            command=self.delete_participant
        ).pack(side=tk.LEFT, padx=5)
    
    def create_log_tab(self, notebook):
        """创建日志选项卡"""
        log_frame = ttk.Frame(notebook)
        notebook.add(log_frame, text="系统日志")
        
        self.log_text = tk.Text(
            log_frame,
            height=25,
            font=("Consolas", 9),
            bg="#2c3e50",
            fg="#ecf0f1"
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 滚动条
        scrollbar = tk.Scrollbar(self.log_text)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.log_text.yview)
    
    def create_status_bar(self):
        """创建状态栏"""
        status_bar = tk.Frame(self.root, bg="#ecf0f1", height=30)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        status_bar.pack_propagate(False)
        
        # 左侧状态
        self.status_left = tk.Label(
            status_bar, 
            text="就绪 | 模式: 注册", 
            bg="#ecf0f1", 
            font=self.normal_font
        )
        self.status_left.pack(side=tk.LEFT, padx=10)
        
        # 中间状态
        self.status_center = tk.Label(
            status_bar, 
            text="RFID: 未连接", 
            bg="#ecf0f1", 
            font=self.normal_font
        )
        self.status_center.pack(side=tk.LEFT, padx=10, expand=True)
        
        # 右侧状态
        self.status_right = tk.Label(
            status_bar, 
            text=f"数据库: {DB_FILE}", 
            bg="#ecf0f1", 
            font=self.normal_font
        )
        self.status_right.pack(side=tk.RIGHT, padx=10)
    
    def start_rfid_thread(self):
        """启动RFID线程"""
        self.rfid_thread = RFIDReaderThread(
            self.db_manager, 
            self.message_queue,
            self.config['ip'],
            self.config['port']
        )
        self.rfid_thread.daemon = True
        self.rfid_thread.start()
        self.log_message("RFID读取线程已启动")
    
    def process_messages(self):
        """处理消息队列"""
        try:
            while True:
                try:
                    msg_type, data = self.message_queue.get_nowait()
                    
                    if msg_type == "info":
                        self.connection_label.config(text="🟢 " + data, fg="green")
                        self.status_center.config(text=f"RFID: 已连接 ({self.config['ip']})")
                        self.log_message("信息: " + data)
                    elif msg_type == "error":
                        self.connection_label.config(text="🔴 " + data, fg="red")
                        self.status_center.config(text="RFID: 连接失败")
                        self.log_message("错误: " + data, "error")
                    elif msg_type == "register_request":
                        self.handle_register_request(data)
                    elif msg_type == "punch":
                        self.handle_punch(data)
                    elif msg_type == "finish":
                        self.handle_finish(data)
                        
                except queue.Empty:
                    break
        finally:
            self.root.after(100, self.process_messages)
    
    def handle_register_request(self, card_uid: str):
        """处理注册请求"""
        # 防抖：防止短时间内重复弹出窗口
        current_time = time.time()
        if current_time - self.last_registration_time < 2:  # 2秒内不重复处理
            return
        
        self.last_registration_time = current_time
        
        # 检查是否已有注册窗口
        if self.reg_window and self.reg_window.winfo_exists():
            # 如果已有窗口，将其提到最前面
            try:
                self.reg_window.lift()
                self.reg_window.focus_force()
            except:
                pass
            return
        
        # 暂停RFID扫描（仅注册模式时暂停）
        if self.rfid_thread and self.rfid_thread.current_mode == "register":
            self.rfid_thread.set_mode("idle")
            self.status_left.config(text="就绪 | 模式: 暂停 (注册中)")
        
        # 创建注册窗口
        self.reg_window = RegistrationWindow(
            self.root, 
            self.db_manager, 
            card_uid,
            on_registered=self.on_registration_complete,
            on_cancel=self.on_registration_cancel
        )
        
        self.log_message(f"检测到新卡片，弹出注册窗口: {card_uid}")
    
    def on_registration_complete(self):
        """注册完成回调"""
        self.log_message("选手注册完成")
        self.refresh_participants_list()
        self.load_participants()
        self.update_stats()
        
        # 恢复RFID扫描
        if self.rfid_thread:
            self.rfid_thread.set_mode("register")
            self.status_left.config(text="就绪 | 模式: 注册")
        
        # 播放提示音
        self.beep_success()
    
    def on_registration_cancel(self):
        """注册取消回调"""
        self.log_message("注册已取消")
        
        # 恢复RFID扫描
        if self.rfid_thread:
            self.rfid_thread.set_mode("register")
            self.status_left.config(text="就绪 | 模式: 注册")
        
        # 清除注册窗口引用
        self.reg_window = None
    
    def handle_punch(self, data: Dict):
        """处理打卡信息"""
        name = data['name']
        antenna = data['antenna']
        punch_time = data['time']
        card_uid = data.get('card_uid', '未知')
        
        # 更新天线状态
        if antenna in self.antenna_labels:
            label, status = self.antenna_labels[antenna]
            status.config(text="🟢")
            self.root.after(1000, lambda a=antenna: self.reset_antenna_status(a))
        
        # 显示打卡信息
        message = f"[{punch_time}] {name} 在检查点{antenna} 打卡 (卡号: {card_uid})"
        self.append_punch_text(message)
        self.log_message(f"打卡: {name} 在检查点{antenna}")
        
        # 更新统计信息
        self.update_stats()
    
    def handle_finish(self, data: Dict):
        """处理完成比赛"""
        name = data['name']
        finish_time = data['time']
        
        message = f"🎉 {name} 已完成比赛! 完成时间: {finish_time}"
        self.append_punch_text(message)
        self.append_punch_text("=" * 60)
        self.log_message(f"完成: {name} 已完成比赛")
        
        # 播放完成提示音
        self.beep_finish()
        
        # 更新统计信息
        self.update_stats()
    
    def reset_antenna_status(self, antenna: int):
        """重置天线状态"""
        if antenna in self.antenna_labels:
            label, status = self.antenna_labels[antenna]
            status.config(text="🔴")
    
    def append_punch_text(self, text: str):
        """向打卡文本框添加文本"""
        self.punch_text.insert(tk.END, text + "\n")
        self.punch_text.see(tk.END)
    
    def log_message(self, message: str, level: str = "info"):
        """记录日志消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        if level == "error":
            tag = "ERROR"
            color = "#e74c3c"
        elif level == "warning":
            tag = "WARN"
            color = "#f39c12"
        else:
            tag = "INFO"
            color = "#3498db"
        
        log_entry = f"[{timestamp}] [{tag}] {message}\n"
        self.log_text.insert(tk.END, log_entry)
        self.log_text.tag_add(tag, f"end-2l", "end-1l")
        self.log_text.tag_config(tag, foreground=color)
        self.log_text.see(tk.END)
    
    def start_race(self):
        """开始比赛"""
        # 检查是否有注册的选手
        participants = self.db_manager.get_all_participants_summary()
        if not participants:
            messagebox.showwarning("警告", "没有注册的选手，请先注册选手！")
            return
        
        # 切换到比赛模式
        if self.rfid_thread:
            self.rfid_thread.set_mode("race")
            self.rfid_thread.start_race()
        
        # 记录开始时间
        self.race_start_time = datetime.now()
        self.system_status_label.config(text="状态: 比赛进行中", fg="red")
        self.status_left.config(text="就绪 | 模式: 比赛")
        
        # 更新按钮状态
        self.buttons["🚩 开始比赛"].config(state="disabled")
        self.buttons["🛑 结束比赛"].config(state="normal")
        
        # 清空打卡信息
        self.punch_text.delete(1.0, tk.END)
        self.append_punch_text("=" * 60)
        self.append_punch_text(f"比赛开始时间: {self.race_start_time.strftime('%H:%M:%S')}")
        self.append_punch_text(f"参赛选手: {len(participants)}人")
        self.append_punch_text("=" * 60)
        
        # 开始计时器
        self.update_timer()
        
        self.log_message("比赛开始")
        messagebox.showinfo("比赛开始", "比赛已开始，开始轮询所有检查点！")
    
    def end_race(self):
        """结束比赛"""
        if self.rfid_thread:
            self.rfid_thread.stop_race()
            self.rfid_thread.set_mode("register")
        
        self.system_status_label.config(text="状态: 比赛已结束", fg="blue")
        self.status_left.config(text="就绪 | 模式: 注册")
        
        # 更新按钮状态
        self.buttons["🚩 开始比赛"].config(state="normal")
        self.buttons["🛑 结束比赛"].config(state="disabled")
        
        # 停止计时器
        if self.timer_job:
            self.root.after_cancel(self.timer_job)
        
        self.append_punch_text("=" * 60)
        self.append_punch_text(f"比赛结束时间: {datetime.now().strftime('%H:%M:%S')}")
        self.append_punch_text("=" * 60)
        
        self.log_message("比赛结束")
        messagebox.showinfo("比赛结束", "比赛已结束，停止轮询检查点。")
    
    def update_timer(self):
        """更新计时器"""
        if self.race_start_time and self.buttons["🚩 开始比赛"]['state'] == 'disabled':
            elapsed = datetime.now() - self.race_start_time
            total_seconds = int(elapsed.total_seconds())
            
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            self.time_label.config(text=f"比赛时间: {time_str}")
            
            # 每100ms更新一次
            self.timer_job = self.root.after(100, self.update_timer)
    
    def manual_register_submit(self):
        """手动注册提交"""
        card_uid = self.manual_card_entry.get().strip()
        name = self.manual_name_entry.get().strip()
        
        if not card_uid or not name:
            messagebox.showerror("错误", "卡号和姓名不能为空！")
            return
        
        age_str = self.manual_age_entry.get().strip()
        try:
            age = int(age_str) if age_str else 0
        except ValueError:
            messagebox.showerror("错误", "年龄必须是数字！")
            return
        
        gender = self.manual_gender_var.get()
        team = self.manual_team_entry.get().strip()
        phone = self.manual_phone_entry.get().strip()
        
        success, message, _ = self.db_manager.register_participant(
            card_uid, name, gender, age, team, phone
        )
        
        if success:
            messagebox.showinfo("成功", message)
            self.reset_manual_form()
            self.refresh_participants_list()
            self.load_participants()
            self.update_stats()
            
            self.log_message(f"手动注册选手: {name} ({team})")
            self.beep_success()
        else:
            messagebox.showerror("错误", message)
    
    def reset_manual_form(self):
        """重置手动注册表单"""
        self.manual_card_entry.delete(0, tk.END)
        self.manual_name_entry.delete(0, tk.END)
        self.manual_age_entry.delete(0, tk.END)
        self.manual_team_entry.delete(0, tk.END)
        self.manual_phone_entry.delete(0, tk.END)
        self.manual_gender_var.set("男")
    
    def manual_register(self):
        """手动注册（打开手动注册标签页）"""
        # 切换到注册标签页
        notebook = self.root.winfo_children()[1].winfo_children()[0]
        notebook.select(0)  # 选择第一个标签页（注册）
        
        # 聚焦到卡号输入框
        self.manual_card_entry.focus_set()
    
    def refresh_participants_list(self):
        """刷新已注册选手列表"""
        # 清空现有数据
        for item in self.reg_tree.get_children():
            self.reg_tree.delete(item)
        
        # 加载数据
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT name, team, card_uid, 
                   strftime('%H:%M:%S', registration_time)
            FROM participants
            ORDER BY registration_time DESC
        ''')
        
        participants = cursor.fetchall()
        conn.close()
        
        # 插入数据
        for i, (name, team, card_uid, reg_time) in enumerate(participants, 1):
            self.reg_tree.insert("", tk.END, values=(i, name, team, card_uid, reg_time))
    
    def load_participants(self):
        """加载选手数据"""
        # 清空现有数据
        for item in self.part_tree.get_children():
            self.part_tree.delete(item)
        
        # 加载数据
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, team, card_uid, age, gender, phone
            FROM participants
            ORDER BY name
        ''')
        
        participants = cursor.fetchall()
        conn.close()
        
        # 插入数据
        for p in participants:
            self.part_tree.insert("", tk.END, values=p)
    
    def search_participants(self):
        """搜索选手"""
        search_term = self.search_var.get().lower()
        
        # 清空现有数据
        for item in self.part_tree.get_children():
            self.part_tree.delete(item)
        
        # 加载数据
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, team, card_uid, age, gender, phone
            FROM participants
            WHERE LOWER(name) LIKE ? OR LOWER(team) LIKE ? OR LOWER(card_uid) LIKE ?
            ORDER BY name
        ''', (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"))
        
        participants = cursor.fetchall()
        conn.close()
        
        # 插入数据
        for p in participants:
            self.part_tree.insert("", tk.END, values=p)
    
    def update_stats(self):
        """更新统计信息"""
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM participants")
        total_participants = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM punch_records")
        total_punches = cursor.fetchone()[0]
        
        conn.close()
        
        self.stats_label.config(text=f"选手: {total_participants}人 | 打卡: {total_punches}次")
        self.progress_label.config(text=f"注册进度: {total_participants}人")
        
        if total_participants > 0:
            self.progress_bar['value'] = 100
        else:
            self.progress_bar['value'] = 0
    
    def show_results(self):
        """显示比赛结果"""
        results_window = tk.Toplevel(self.root)
        results_window.title("比赛成绩")
        results_window.geometry("900x600")
        
        # 创建Treeview
        tree_frame = tk.Frame(results_window)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar_y = ttk.Scrollbar(tree_frame)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        scrollbar_x = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        columns = ("排名", "姓名", "队伍", "卡号", "完成检查点", "首次打卡", "最后打卡", "进度")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                           yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        # 设置列宽
        column_widths = [50, 100, 80, 120, 100, 120, 120, 80]
        for col, width in zip(columns, column_widths):
            tree.heading(col, text=col)
            tree.column(col, width=width)
        
        tree.pack(fill=tk.BOTH, expand=True)
        scrollbar_y.config(command=tree.yview)
        scrollbar_x.config(command=tree.xview)
        
        # 获取数据
        participants = self.db_manager.get_all_participants_summary()
        
        # 按完成检查点数量和时间排序
        sorted_participants = sorted(
            participants,
            key=lambda x: (x['checkpoints_visited'], x['last_punch'] if x['last_punch'] != "未打卡" else "9999"),
            reverse=True
        )
        
        # 插入数据
        for i, p in enumerate(sorted_participants, 1):
            progress = f"{p['checkpoints_visited']}/8"
            tree.insert("", tk.END, values=(
                i,
                p['name'],
                p['team'],
                p['card_uid'],
                p['checkpoints_visited'],
                p['first_punch'],
                p['last_punch'],
                progress
            ))
        
        # 按钮
        button_frame = tk.Frame(results_window)
        button_frame.pack(pady=10)
        
        tk.Button(
            button_frame,
            text="📤 导出CSV",
            command=lambda: self.export_results_csv(sorted_participants)
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            button_frame,
            text="🖨️ 打印",
            command=lambda: self.print_results(tree)
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            button_frame,
            text="关闭",
            command=results_window.destroy
        ).pack(side=tk.LEFT, padx=5)
    
    def export_results_csv(self, participants):
        """导出结果到CSV"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["排名", "姓名", "队伍", "卡号", "完成检查点", "首次打卡", "最后打卡"])
                    
                    for i, p in enumerate(participants, 1):
                        writer.writerow([
                            i,
                            p['name'],
                            p['team'],
                            p['card_uid'],
                            p['checkpoints_visited'],
                            p['first_punch'],
                            p['last_punch']
                        ])
                
                messagebox.showinfo("成功", f"数据已导出到: {filename}")
                self.log_message(f"导出数据到: {filename}")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {str(e)}")
    
    def print_results(self, tree):
        """打印结果"""
        try:
            # 这里可以连接打印机，这里只打印到控制台
            items = tree.get_children()
            print("=" * 60)
            print("定向越野比赛成绩")
            print("=" * 60)
            for item in items:
                values = tree.item(item)['values']
                print(f"{values[0]:3} {values[1]:10} {values[2]:8} {values[4]:3}个检查点")
            
            messagebox.showinfo("打印", "成绩已发送到打印机（控制台）")
        except Exception as e:
            messagebox.showerror("打印失败", str(e))
    
    def show_live_ranking(self):
        """显示实时排名"""
        ranking_window = tk.Toplevel(self.root)
        ranking_window.title("实时排名")
        ranking_window.geometry("500x400")
        
        # 排名列表
        frame = tk.Frame(ranking_window)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.ranking_text = tk.Text(frame, height=20, font=("Consolas", 11))
        self.ranking_text.pack(fill=tk.BOTH, expand=True)
        
        # 更新排名
        self.update_live_ranking(ranking_window)
    
    def update_live_ranking(self, window):
        """更新实时排名"""
        if not window.winfo_exists():
            return
        
        participants = self.db_manager.get_all_participants_summary()
        
        # 按完成检查点数量和时间排序
        sorted_participants = sorted(
            participants,
            key=lambda x: (x['checkpoints_visited'], x['last_punch'] if x['last_punch'] != "未打卡" else "9999"),
            reverse=True
        )
        
        # 更新显示
        self.ranking_text.delete(1.0, tk.END)
        self.ranking_text.insert(tk.END, f"{'排名':<4} {'姓名':<10} {'队伍':<8} {'检查点':<6}\n")
        self.ranking_text.insert(tk.END, "=" * 35 + "\n")
        
        for i, p in enumerate(sorted_participants[:10], 1):  # 只显示前10名
            self.ranking_text.insert(tk.END, f"{i:<4} {p['name']:<10} {p['team']:<8} {p['checkpoints_visited']:<6}\n")
        
        # 每5秒更新一次
        window.after(5000, lambda: self.update_live_ranking(window))
    
    def open_settings(self):
        """打开设置窗口"""
        dialog = tk.Toplevel(self.root)
        dialog.title("系统设置")
        dialog.geometry("400x300")
        dialog.resizable(False, False)
        
        # 设置项
        tk.Label(dialog, text="RFID设备IP:", font=self.normal_font).grid(
            row=0, column=0, padx=10, pady=10, sticky=tk.W
        )
        ip_entry = tk.Entry(dialog, width=25, font=self.normal_font)
        ip_entry.insert(0, self.config['ip'])
        ip_entry.grid(row=0, column=1, padx=10, pady=10)
        
        tk.Label(dialog, text="端口:", font=self.normal_font).grid(
            row=1, column=0, padx=10, pady=10, sticky=tk.W
        )
        port_entry = tk.Entry(dialog, width=25, font=self.normal_font)
        port_entry.insert(0, str(self.config['port']))
        port_entry.grid(row=1, column=1, padx=10, pady=10)
        
        tk.Label(dialog, text="轮询间隔(秒):", font=self.normal_font).grid(
            row=2, column=0, padx=10, pady=10, sticky=tk.W
        )
        interval_entry = tk.Entry(dialog, width=25, font=self.normal_font)
        interval_entry.insert(0, str(self.config['polling_interval']))
        interval_entry.grid(row=2, column=1, padx=10, pady=10)
        
        def save_settings():
            try:
                new_ip = ip_entry.get().strip()
                new_port = int(port_entry.get().strip())
                new_interval = float(interval_entry.get().strip())
                
                if new_interval <= 0:
                    raise ValueError("轮询间隔必须大于0")
                
                self.config['ip'] = new_ip
                self.config['port'] = new_port
                self.config['polling_interval'] = new_interval
                
                # 重启RFID线程
                if self.rfid_thread:
                    self.rfid_thread.stop()
                    self.rfid_thread.join(timeout=2)
                
                self.start_rfid_thread()
                
                messagebox.showinfo("成功", "设置已保存并生效！")
                self.log_message(f"系统设置已更新: IP={new_ip}, 端口={new_port}, 间隔={new_interval}s")
                dialog.destroy()
                
            except ValueError as e:
                messagebox.showerror("错误", f"输入无效: {str(e)}")
            except Exception as e:
                messagebox.showerror("错误", f"保存设置失败: {str(e)}")
        
        tk.Button(
            dialog, text="✅ 保存", font=self.normal_font, 
            bg="#27ae60", fg="white", command=save_settings
        ).grid(row=3, column=0, columnspan=2, pady=20)
        
        tk.Button(
            dialog, text="❌ 取消", font=self.normal_font, 
            command=dialog.destroy
        ).grid(row=4, column=0, columnspan=2)
    
    def clear_data_confirm(self):
        """确认清除数据"""
        if messagebox.askyesno("确认", "确定要清除所有数据吗？\n此操作将删除所有选手和打卡记录，且不可恢复！"):
            self.clear_data()
    
    def clear_data(self):
        """清除数据"""
        try:
            self.db_manager.clear_all_data()
            self.refresh_participants_list()
            self.load_participants()
            self.update_stats()
            self.punch_text.delete(1.0, tk.END)
            messagebox.showinfo("成功", "所有数据已清除")
            self.log_message("清除所有数据", "warning")
        except Exception as e:
            messagebox.showerror("错误", f"清除数据失败: {str(e)}")
            self.log_message(f"清除数据失败: {str(e)}", "error")
    
    def export_data(self):
        """导出数据"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        
        if filename:
            try:
                self.db_manager.export_to_csv(filename)
                messagebox.showinfo("成功", f"数据已导出到: {filename}")
                self.log_message(f"导出数据到: {filename}")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {str(e)}")
                self.log_message(f"导出失败: {str(e)}", "error")
    
    def save_punch_log(self):
        """保存打卡日志"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("日志文件", "*.log"), ("所有文件", "*.*")]
        )
        
        if filename:
            try:
                log_content = self.punch_text.get(1.0, tk.END)
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write("定向越野打卡记录\n")
                    f.write("=" * 50 + "\n")
                    f.write(log_content)
                messagebox.showinfo("成功", f"日志已保存到: {filename}")
                self.log_message(f"保存打卡日志到: {filename}")
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {str(e)}")
                self.log_message(f"保存日志失败: {str(e)}", "error")
    
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
    
    def beep_finish(self):
        """播放完成提示音"""
        try:
            import winsound
            winsound.Beep(1000, 300)
            time.sleep(0.1)
            winsound.Beep(1200, 300)
        except:
            try:
                print('\a\a')
            except:
                pass
    
    def view_participant_details(self):
        """查看选手详情"""
        selection = self.part_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择一个选手")
            return
        
        item = self.part_tree.item(selection[0])
        values = item['values']
        
        participant_id = values[0]
        progress = self.db_manager.get_participant_progress(participant_id)
        
        dialog = tk.Toplevel(self.root)
        dialog.title(f"选手详情 - {progress['name']}")
        dialog.geometry("500x400")
        
        tk.Label(dialog, text=f"姓名: {progress['name']}", font=self.heading_font).pack(pady=10)
        tk.Label(dialog, text=f"队伍: {progress['team']}").pack(pady=5)
        tk.Label(dialog, text=f"进度: {progress['completed_count']}/{progress['total_checkpoints']}").pack(pady=5)
        
        # 打卡记录
        frame = tk.LabelFrame(dialog, text="打卡记录")
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        text = tk.Text(frame, height=15, font=("Consolas", 10))
        text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        if progress['records']:
            for record in progress['records']:
                text.insert(tk.END, f"{record[0]} (天线{record[1]}) - {record[2]}\n")
        else:
            text.insert(tk.END, "暂无打卡记录")
        
        text.config(state="disabled")
    
    def edit_participant(self):
        """编辑选手"""
        selection = self.part_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择一个选手")
            return
        
        item = self.part_tree.item(selection[0])
        values = item['values']
        
        dialog = tk.Toplevel(self.root)
        dialog.title(f"编辑选手 - {values[1]}")
        dialog.geometry("400x300")
        dialog.resizable(False, False)
        
        tk.Label(dialog, text="姓名:", font=self.normal_font).grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
        name_entry = tk.Entry(dialog, width=25, font=self.normal_font)
        name_entry.insert(0, values[1])
        name_entry.grid(row=0, column=1, padx=10, pady=10)
        
        tk.Label(dialog, text="队伍:", font=self.normal_font).grid(row=1, column=0, padx=10, pady=10, sticky=tk.W)
        team_entry = tk.Entry(dialog, width=25, font=self.normal_font)
        team_entry.insert(0, values[2])
        team_entry.grid(row=1, column=1, padx=10, pady=10)
        
        def save_changes():
            new_name = name_entry.get().strip()
            new_team = team_entry.get().strip()
            
            if not new_name:
                messagebox.showerror("错误", "姓名不能为空！", parent=dialog)
                return
            
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "UPDATE participants SET name = ?, team = ? WHERE id = ?",
                    (new_name, new_team, values[0])
                )
                conn.commit()
                messagebox.showinfo("成功", "选手信息已更新！", parent=dialog)
                dialog.destroy()
                self.load_participants()
                self.log_message(f"编辑选手: {values[1]} -> {new_name}")
            except Exception as e:
                messagebox.showerror("错误", f"更新失败: {str(e)}", parent=dialog)
            finally:
                conn.close()
        
        tk.Button(
            dialog, text="✅ 保存", font=self.normal_font, 
            bg="#27ae60", fg="white", command=save_changes
        ).grid(row=2, column=0, columnspan=2, pady=20)
    
    def delete_participant(self):
        """删除选手"""
        selection = self.part_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择一个选手")
            return
        
        item = self.part_tree.item(selection[0])
        values = item['values']
        
        if messagebox.askyesno("确认", f"确定要删除选手 {values[1]} 吗？\n此操作将删除该选手的所有打卡记录！"):
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM punch_records WHERE participant_id = ?", (values[0],))
                cursor.execute("DELETE FROM participants WHERE id = ?", (values[0],))
                conn.commit()
                
                self.load_participants()
                self.update_stats()
                messagebox.showinfo("成功", f"选手 {values[1]} 已删除")
                self.log_message(f"删除选手: {values[1]}", "warning")
            except Exception as e:
                messagebox.showerror("错误", f"删除失败: {str(e)}")
            finally:
                conn.close()
    
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
        self.refresh_participants_list()
        self.load_participants()
        self.update_stats()
        
        # 启动主循环
        self.root.mainloop()

# ==================== 主程序入口 ====================
if __name__ == "__main__":
    print("=" * 60)
    print("定向越野管理系统 v2.1")
    print("=" * 60)
    print(f"数据库文件: {DB_FILE}")
    print(f"RFID设备: {IP}:{PORT}")
    print("正在启动系统...")
    
    try:
        app = OrienteeringUI()
        app.run()
    except Exception as e:
        print(f"启动失败: {e}")
        import traceback
        traceback.print_exc()
        input("按Enter键退出...")



        