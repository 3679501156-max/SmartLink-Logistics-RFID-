
import socket
import threading
import time
import struct
from typing import Optional, List, Dict

# ==================== 配置 ====================
HOST = '127.0.0.1'
PORT = 4001

# ==================== 仿真数据 ====================
# 我们可以通过命令行动态修改这个字典来模拟卡片
# 格式: {antenna_no: card_uid}
SIMULATED_CARDS: Dict[int, Optional[str]] = {
    1: "11223344",
    2: None,
    3: None,
    4: None,
    5: None,
    6: None,
    7: None,
    8: None,
}

# ==================== 辅助函数 ====================
def calculate_checksum(byte_list: List[int]) -> int:
    """计算异或校验码"""
    return_value = 0
    for byte in byte_list:
        return_value ^= byte
    return return_value

def build_response(command_low: int, command_high: int, status: int, data_bytes: List[int]) -> bytes:
    """
    构建响应
    格式: AA BB [数据长度] 00 00 [命令低字节] [命令高字节] [状态] [数据包] [校验码]
    """
    # 命令头
    response = [0xAA, 0xBB]

    # 数据长度: 设备号(2) + 命令码(2) + 状态(1) + 数据包长度 + 校验码(1)
    data_len = 2 + 2 + 1 + len(data_bytes) + 1
    response.extend([data_len & 0xFF, (data_len >> 8) & 0xFF])

    # 设备号 (00 00)
    response.extend([0x00, 0x00])

    # 命令码
    response.extend([command_low, command_high])

    # 状态
    response.append(status)

    # 数据包
    response.extend(data_bytes)

    # 校验码 (从命令码开始)
    checksum_bytes = [command_low, command_high, status] + data_bytes
    checksum = calculate_checksum(checksum_bytes)
    response.append(checksum)

    return bytes(response)

# ==================== 客户端处理线程 ====================
class ClientThread(threading.Thread):
    """处理单个客户端连接的线程"""

    def __init__(self, conn: socket.socket, addr: tuple):
        super().__init__()
        self.conn = conn
        self.addr = addr
        self.current_antenna = 1
        print(f"[连接成功] {self.addr} 已连接")

    def run(self):
        try:
            while True:
                data = self.conn.recv(1024)
                if not data:
                    break

                # 解析收到的命令 (简易版)
                if len(data) >= 9 and data[0:2] == b'\xaa\xbb':
                    cmd_low = data[6]
                    cmd_high = data[7]
                    command = (cmd_high << 8) | cmd_low
                    cmd_data = data[8:-1] # 提取数据部分

                    print(f"[收到命令] 0x{command:04X} from {self.addr}")

                    # 根据命令进行响应
                    self.handle_command(command, list(cmd_data))

        except (ConnectionResetError, BrokenPipeError):
            print(f"[连接断开] {self.addr} 异常断开")
        finally:
            print(f"[连接关闭] {self.addr} 已关闭")
            self.conn.close()

    def handle_command(self, command: int, cmd_data: List[int]):
        """根据命令生成并发送响应"""
        response = b''

        # --- 天线切换 (0x11FF) ---
        if command == 0x11FF:
            antenna_no = cmd_data[0]
            if 1 <= antenna_no <= 8:
                self.current_antenna = antenna_no
                print(f"[仿真] 切换到天线 {self.current_antenna}")
                # 成功响应，无数据
                response = build_response(0xFF, 0x11, 0x00, [])
            else:
                # 失败响应
                response = build_response(0xFF, 0x11, 0x01, [])

        # --- 寻卡 (0x0201) ---
        elif command == 0x0201:
            card_uid = SIMULATED_CARDS.get(self.current_antenna)
            if card_uid:
                print(f"[仿真] 在天线 {self.current_antenna} 发现卡")
                # 成功响应，返回卡片类型 (ATQA)，这里用固定值
                response = build_response(0x01, 0x02, 0x00, [0x04, 0x00])
            else:
                # 失败响应 (找不到卡)
                response = build_response(0x01, 0x02, 0x01, [])

        # --- 读UID (0x0202) ---
        elif command == 0x0202:
            card_uid = SIMULATED_CARDS.get(self.current_antenna)
            if card_uid:
                print(f"[仿真] 在天线 {self.current_antenna} 读取到UID: {card_uid}")
                # 成功响应，返回UID
                uid_bytes = list(bytes.fromhex(card_uid))
                response = build_response(0x02, 0x02, 0x00, uid_bytes)
            else:
                # 失败响应
                response = build_response(0x02, 0x02, 0x01, [])

        else:
            print(f"[警告] 未知的命令: 0x{command:04X}")
            # 返回一个通用的错误响应
            response = build_response(command & 0xFF, (command >> 8) & 0xFF, 0xEE, [])

        if response:
            self.conn.sendall(response)

# ==================== 主服务器逻辑 ====================
def main_server():
    """主服务器函数"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"[服务器启动] 仿真服务器正在监听 {HOST}:{PORT}")

        while True:
            conn, addr = s.accept()
            thread = ClientThread(conn, addr)
            thread.start()

# ==================== 命令行交互 ====================
def command_interface():
    """命令行交互，用于控制仿真器"""
    print("\n================ RFID 仿真器控制台 ================")
    print("命令格式:")
    print("  set <天线号> <卡号>  - 在指定天线放置一张卡 (例如: set 1 AABBCCDD)")
    print("  del <天线号>         - 从指定天线移除卡片 (例如: del 1)")
    print("  show                 - 显示当前所有天线的卡片状态")
    print("  exit                 - 退出仿真器")
    print("====================================================\n")

    while True:
        try:
            cmd_input = input("> ").strip().lower().split()
            if not cmd_input:
                continue

            command = cmd_input[0]

            if command == 'exit':
                break
            elif command == 'show':
                print("[当前状态]")
                for ant, uid in SIMULATED_CARDS.items():
                    print(f"  天线 {ant}: {uid or '无卡'}")
            elif command == 'set' and len(cmd_input) == 3:
                ant_no = int(cmd_input[1])
                card_uid = cmd_input[2].upper()
                if 1 <= ant_no <= 8 and len(card_uid) == 8:
                    SIMULATED_CARDS[ant_no] = card_uid
                    print(f"[成功] 已在天线 {ant_no} 放置卡 {card_uid}")
                else:
                    print("[错误] 无效的参数。天线号1-8, 卡号为8位十六进制数")
            elif command == 'del' and len(cmd_input) == 2:
                ant_no = int(cmd_input[1])
                if 1 <= ant_no <= 8:
                    SIMULATED_CARDS[ant_no] = None
                    print(f"[成功] 已从天线 {ant_no} 移除卡片")
                else:
                    print("[错误] 无效的天线号")
            else:
                print("[错误] 未知或无效的命令")

        except (ValueError, IndexError):
            print("[错误] 命令格式不正确")
        except Exception as e:
            print(f"[发生异常] {e}")

    print("[正在关闭] 仿真器正在关闭...")
    # 简单的退出方式，实际应用中可能需要更优雅地关闭所有线程
    import os
    os._exit(0)

if __name__ == "__main__":
    # 在后台线程运行服务器
    server_thread = threading.Thread(target=main_server, daemon=True)
    server_thread.start()

    # 在主线程运行命令行交互
    command_interface()