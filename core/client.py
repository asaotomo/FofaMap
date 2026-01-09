import httpx
import base64
import json
import asyncio
from config import settings
from utils.logger import logger


class FofaClient:
    def __init__(self):
        # 直接指定官方地址，防止配置文件缺失报错
        self.base_url = "https://fofa.info"
        self.email = settings.userinfo.email
        self.key = settings.userinfo.key
        self.headers = {
            "User-Agent": "FofaMapV2/2.0 (By Hx0 Team)"
        }
        # 增加超时时间到 60s，防止复杂查询超时
        self.client_args = {"http2": True, "verify": False, "timeout": 60}

    async def check_login(self) -> dict:
        """ 验证账号并返回用户信息 """
        url = f"{self.base_url}/api/v1/info/my"
        params = {"email": self.email, "key": self.key}

        async with httpx.AsyncClient(**self.client_args) as client:
            try:
                resp = await client.get(url, params=params, headers=self.headers)
                data = resp.json()
                if data.get("error"):
                    logger.error(f"登录失败: {data.get('errmsg')}")
                    return None
                return data
            except Exception as e:
                logger.error(f"登录请求异常: {e}")
                return None

    async def search(self, query_str: str, page: int = 1, fields: str = None):
        """ 执行搜索 (带智能重试与降级) """
        api_url = f"{self.base_url}/api/v1/search/all"
        qbase64 = base64.b64encode(query_str.encode('utf-8')).decode()

        current_fields = fields if fields else settings.search.fields
        safe_fields = "host,ip,port,protocol,title,domain,country,city,server"

        params = {
            "email": self.email,
            "key": self.key,
            "qbase64": qbase64,
            "page": page,
            "size": settings.search.size,
            "fields": current_fields,
            "full": str(settings.search.full).lower()
        }

        async with httpx.AsyncClient(**self.client_args) as client:
            # [修改] 增加重试循环 (默认3次)
            for attempt in range(3):
                try:
                    if "host,protocol,ip,port" not in current_fields and attempt == 0:
                        logger.info(f"正在查询第 {page} 页...")

                    resp = await client.get(api_url, params=params, headers=self.headers)

                    # [修改] 处理 HTTP 429 Too Many Requests
                    if resp.status_code == 429:
                        logger.warning(f"触发速率限制 (429)，休眠 3 秒后重试 ({attempt + 1}/3)...")
                        await asyncio.sleep(3)
                        continue

                    try:
                        result = resp.json()
                    except:
                        # JSON 解析失败通常是网络问题，稍微等待后重试
                        await asyncio.sleep(1)
                        continue

                    if result.get("error"):
                        errmsg = str(result.get("errmsg", ""))

                        # [修改] 处理 FOFA 业务层限速 (45012)
                        if "45012" in errmsg or "请求速度过快" in errmsg:
                            logger.warning(f"触发 FOFA 频率限制 (45012)，休眠 2 秒后重试 ({attempt + 1}/3)...")
                            await asyncio.sleep(2)
                            continue

                        # 处理权限不足 (820001)，保留你原来的降级逻辑
                        if "820001" in errmsg or "权限" in errmsg:
                            if current_fields == safe_fields:
                                return []
                            logger.warning("触发降级机制 -> 切换基础字段重试...")
                            params["fields"] = safe_fields
                            # 降级请求直接执行，不再套娃重试
                            retry_resp = await client.get(api_url, params=params, headers=self.headers)
                            result = retry_resp.json()
                        else:
                            logger.error(f"查询出错: {errmsg}")
                            return []

                    return result.get("results", [])

                except Exception as e:
                    logger.error(f"查询请求异常: {e}")
                    await asyncio.sleep(1)

            return []

    async def host_search(self, host: str):
        """ Host 聚合搜索 (带重试) """
        api_url = f"{self.base_url}/api/v1/host/{host}"
        params = {"email": self.email, "key": self.key, "detail": "true"}

        async with httpx.AsyncClient(**self.client_args) as client:
            for attempt in range(3):
                try:
                    resp = await client.get(api_url, params=params, headers=self.headers)

                    if resp.status_code == 429:
                        await asyncio.sleep(3)
                        continue

                    data = resp.json()
                    # 简单判断是否限速
                    if data.get("error") and ("45012" in str(data.get("errmsg"))):
                        await asyncio.sleep(2)
                        continue

                    return data
                except Exception as e:
                    logger.error(f"Host聚合查询异常: {e}")
                    await asyncio.sleep(1)
            return {}

    async def stats_search(self, query_str: str, fields: str = "title"):
        api_url = f"{self.base_url}/api/v1/search/stats"
        qbase64 = base64.b64encode(query_str.encode('utf-8')).decode()
        params = {"email": self.email, "key": self.key, "qbase64": qbase64, "fields": fields}

        async with httpx.AsyncClient(**self.client_args) as client:
            try:
                resp = await client.get(api_url, params=params, headers=self.headers)
                return resp.json()
            except Exception:
                return {}