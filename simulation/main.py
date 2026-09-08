from core.config_loader import ConfigLoader
from core.database import DatabaseManager
from gui.main_window import OrienteeringUI

def main():
    # 加载配置
    config_loader = ConfigLoader()
    
    # 初始化数据库
    db_file = config_loader.get("database.filename", "orienteering.db")
    db_manager = DatabaseManager(db_file)
    
    # 启动UI
    app_config = {
        'ip': config_loader.get("server.ip", "127.0.0.1"),
        'port': config_loader.get("server.port", 4001)
    }
    
    app = OrienteeringUI(db_manager, app_config)
    app.run()

if __name__ == "__main__":
    main()
