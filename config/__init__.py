import os

import yaml
from pydantic import BaseModel, Field
from pathlib import Path

# --- 定义数据模型 (对应 settings.yaml 的结构) ---

class UserInfo(BaseModel):
    email: str
    key: str
    deepseek_api_key: str = ""
    # --- [畅想1: 新增映射字段] ---
    # 增加对 base_url 和 model 的读取支持，否则 Pydantic 会忽略它们
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"


class SearchConfig(BaseModel):
    fields: str = "host,protocol,ip,port,title,domain,country"
    size: int = 100
    full: bool = False
    start_page: int = 1
    end_page: int = 2


class FastCheckConfig(BaseModel):
    check_alive: bool = True
    timeout: int = 5


class SystemConfig(BaseModel):
    logger: bool = True
    sheet_merge: bool = True
    concurrency: int = 10
    export_format: str = "xlsx"
    output_dir: str = "results"


class Config(BaseModel):
    userinfo: UserInfo
    search: SearchConfig
    fast_check: FastCheckConfig = Field(default_factory=FastCheckConfig)
    system: SystemConfig = Field(default_factory=SystemConfig)


# --- 加载逻辑 ---

def load_config() -> Config:
    config_path = Path(__file__).parent / "settings.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"配置文件未找到: {config_path}，请参照模板创建。")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            # 现在 Config(**data) 会正确映射 base_url 和 model 了
            config = Config(**data)
    except Exception as e:
        print(f"[!] 配置文件解析失败: {e}")
        print("[!] 请检查 config/settings.yaml 的格式是否正确")
        exit(1)

    # 环境变量优先级高于 settings.yaml，便于在 mcp.json 的 "env" 中直接配置凭据：
    #   "env": { "FOFA_EMAIL": "your_email@example.com", "FOFA_KEY": "your_fofa_api_key" }
    env_email = os.environ.get("FOFA_EMAIL")
    env_key = os.environ.get("FOFA_KEY")
    if env_email:
        config.userinfo.email = env_email
    if env_key:
        config.userinfo.key = env_key

    return config


# 初始化全局单例配置
settings = load_config()
