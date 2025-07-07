"""
项目配置文件
统一管理凭据路径、项目设置等配置
"""

import os
import glob
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.absolute()

# 凭据目录
CREDENTIALS_DIR = PROJECT_ROOT / "credentials"

def get_service_account_key_path():
    """
    自动查找服务账户密钥文件
    优先级：
    1. 环境变量 GOOGLE_APPLICATION_CREDENTIALS
    2. credentials目录下的.json文件
    3. 项目根目录下的.json文件（兼容性）
    """
    # 优先使用环境变量
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
    
    # 查找credentials目录下的.json文件
    if CREDENTIALS_DIR.exists():
        json_files = list(CREDENTIALS_DIR.glob("*.json"))
        if json_files:
            return str(json_files[0])  # 返回第一个找到的.json文件
    
    # 兼容性：查找项目根目录下的.json文件
    root_json_files = list(PROJECT_ROOT.glob("*-key.json"))
    if root_json_files:
        return str(root_json_files[0])
    
    # 如果都没找到，返回None
    return None

def setup_google_credentials():
    """
    设置Google认证凭据
    """
    key_path = get_service_account_key_path()
    if key_path and os.path.exists(key_path):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path
        print(f"✅ 已设置Google认证凭据: {key_path}")
        return True
    else:
        print(f"❌ 未找到Google认证凭据文件")
        print(f"请确保凭据文件位于以下位置之一：")
        print(f"   - {CREDENTIALS_DIR}")
        print(f"   - 或设置环境变量 GOOGLE_APPLICATION_CREDENTIALS")
        return False

# 项目配置
PROJECT_CONFIG = {
    "project_id": "cy-aispeci-demo",
    "location": "us-central1",
    "endpoint_id": "7934957714357092352",
    "bucket_name": "vertex_ai_rag_demo"
}

# 服务器配置
SERVER_CONFIG = {
    "host": "0.0.0.0",
    "port": 8080,
    "debug": False
}

# 路径配置
PATHS = {
    "project_root": PROJECT_ROOT,
    "credentials_dir": CREDENTIALS_DIR,
    "cache_dir": PROJECT_ROOT / "cache",
    "logs_dir": PROJECT_ROOT / "logs",
    "docs_dir": PROJECT_ROOT / "docs",
    "src_dir": PROJECT_ROOT / "src"
}

# 确保必要的目录存在
for path in [PATHS["cache_dir"], PATHS["logs_dir"], PATHS["credentials_dir"]]:
    path.mkdir(exist_ok=True)

if __name__ == "__main__":
    print("🔧 项目配置信息:")
    print(f"📁 项目根目录: {PROJECT_ROOT}")
    print(f"🔑 凭据目录: {CREDENTIALS_DIR}")
    print(f"📄 服务账户密钥: {get_service_account_key_path()}")
    print(f"⚙️  配置: {PROJECT_CONFIG}")
    
    # 测试认证设置
    if setup_google_credentials():
        print("✅ Google认证配置成功")
    else:
        print("❌ Google认证配置失败") 