import sqlite3
from typing import Optional, Dict, List, Tuple
import os

class DatabaseManager:
    """数据库管理类，负责数据库的CRUD操作"""
    
    def __init__(self, db_file: str):
        self.db_file = db_file
        self.init_database()
    
    def init_database(self):
        """初始化数据库表结构"""
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
        
        # 初始化检查点数据
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
        import csv
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['姓名', '队伍', '卡号', '检查点', '打卡时间'])
            writer.writerows(data)
