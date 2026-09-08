import threading
import time
import queue
from datetime import datetime
from typing import Optional, Dict
from core.database import DatabaseManager
from core.rfid import RFIDWiFiReader

class RFIDReaderThread(threading.Thread):
    """RFID读取线程"""
    
    def __init__(self, db_manager: DatabaseManager, message_queue: queue.Queue,
                 ip: str, port: int):
        super().__init__()
        self.db_manager = db_manager
        self.message_queue = message_queue
        self.ip = ip
        self.port = port
        self.running = True
        self.race_started = False
        self.current_mode = "register"  # register, race, or idle
        self.reader: Optional[RFIDWiFiReader] = None
        self.polling_interval = 0.3
        self.last_read = {}  # {(card_uid, antenna): timestamp}
        
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
            participant = self.db_manager.get_participant_by_card(card_uid)
            if not participant:
                key = (card_uid, 1)
                current_time = time.time()
                if key in self.last_read and current_time - self.last_read[key] < 10:
                    return
                self.last_read[key] = current_time
                self.message_queue.put(("register_request", card_uid))
        time.sleep(0.5)
    
    def _race_mode(self):
        """比赛模式：轮询所有天线"""
        for antenna in range(1, 9):
            if not self.running: break
            card_uid = self._read_single_antenna(antenna)
            if card_uid:
                self._process_punch(card_uid, antenna)
            time.sleep(self.polling_interval)
    
    def _read_single_antenna(self, antenna: int) -> Optional[str]:
        """读取单个天线的卡片UID"""
        try:
            if not self.reader or not self.reader.connected: return None
            return self.reader.read_card_uid(antenna)
        except Exception: return None
    
    def _process_punch(self, card_uid: str, antenna: int):
        """处理打卡"""
        key = (card_uid, antenna)
        current_time = time.time()
        
        if key in self.last_read and current_time - self.last_read[key] < 30: return
        self.last_read[key] = current_time
        
        participant = self.db_manager.get_participant_by_card(card_uid)
        if not participant: return
        
        success, message = self.db_manager.record_punch(participant['id'], antenna)
        
        if success:
            current_time_str = datetime.now().strftime("%H:%M:%S")
            self.message_queue.put(("punch", {
                'name': participant['name'],
                'antenna': antenna,
                'time': current_time_str,
                'card_uid': card_uid
            }))
            if antenna == 8:
                self.message_queue.put(("finish", {
                    'name': participant['name'],
                    'time': current_time_str
                }))
    
    def set_mode(self, mode: str):
        if mode in ["register", "race", "idle"]:
            self.current_mode = mode
    
    def start_race(self): self.race_started = True
    def stop_race(self): self.race_started = False
    def stop(self): self.running = False
