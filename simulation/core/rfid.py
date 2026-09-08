import socket
from typing import Optional, Dict, List

class RFIDWiFiReader:
    """RFID读卡器通信类"""
    
    def __init__(self, ip: str, port: int):
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
        """构建指令"""
        cmd = [0xAA, 0xBB]
        data_len = 2 + 2 + len(data_bytes) + 1
        cmd.extend([data_len & 0xFF, (data_len >> 8) & 0xFF])
        cmd.extend([0x00, 0x00])
        cmd.extend([command_low, command_high])
        cmd.extend(data_bytes)
        checksum_bytes = [command_low, command_high] + data_bytes
        checksum = self.calculate_checksum(checksum_bytes)
        cmd.append(checksum)
        return bytes(cmd)
    
    def send_command(self, command: bytes, description: str = "", timeout: float = 2.0) -> Optional[bytes]:
        """发送命令并接收响应"""
        if not self.sock or not self.connected:
            return None
        
        try:
            self.sock.settimeout(0.1)
            try: self.sock.recv(4096)
            except: pass
            
            self.sock.sendall(command)
            self.sock.settimeout(timeout)
            return self.sock.recv(1024)
        except Exception:
            return None
    
    def select_antenna(self, antenna_no: int) -> bool:
        """选择天线"""
        if not (1 <= antenna_no <= 8): return False
        command = self.build_command(0xFF, 0x11, [antenna_no])
        response = self.send_command(command)
        if response:
            parsed = self.parse_response(response)
            if parsed and parsed.get('status_code') == 0x00:
                self.current_antenna = antenna_no
                return True
        return False
    
    def search_card(self) -> Optional[bytes]:
        """寻卡"""
        command = self.build_command(0x01, 0x02, [0x52])
        return self.send_command(command)
    
    def anticollision_read_uid(self) -> Optional[bytes]:
        """防碰撞读UID"""
        command = self.build_command(0x02, 0x02, [0x04])
        return self.send_command(command)
    
    def parse_response(self, response: bytes) -> Optional[Dict]:
        """解析响应数据"""
        if len(response) < 9 or response[0:2] != b'\xAA\xBB': return None
        cmd_low, cmd_high = response[6], response[7]
        command = (cmd_high << 8) | cmd_low
        status = response[8]
        
        result = {'command': f"0x{command:04X}", 'status_code': status}
        
        if command == 0x0202 and status == 0x00 and len(response) >= 13:
            result['uid'] = response[9:13].hex().upper()
        
        return result
    
    def read_card_uid(self, antenna_no: int) -> Optional[str]:
        """读取指定天线的卡片UID"""
        if not self.select_antenna(antenna_no): return None
        search_res = self.search_card()
        if not search_res or self.parse_response(search_res).get('status_code') != 0: return None
        uid_res = self.anticollision_read_uid()
        if not uid_res: return None
        return self.parse_response(uid_res).get('uid')
