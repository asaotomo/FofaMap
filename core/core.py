import httpx
import base64
from config import settings
from utils.logger import logger


class FofaClient:
    def __init__(self):
        self.base_url = "https://fofa.info"
        self.email = settings.userinfo.email
        self.key = settings.userinfo.key
        self.headers = {
            "User-Agent": "FofaMapV2/2.0 (By Hx0 Team)"
        }

    async def check_login(self) -> bool:
        """验证账号是否有效"""
        url = f"{self.base_url}/api/v1/info/my"
        params = {"email": self.email, "key": self.key}

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(url, params=params, headers=self.headers, timeout=10)
                data = resp.json()
                if data.get("error"):
                    logger.error(f"登录失败: {data.get('errmsg')}")
                    return False
                logger.info(f"登录成功! 用户名: {data.get('username')} | VIP等级: {data.get('vip_level')}")
                return True
            except Exception as e:
                logger.error(f"网络连接异常: {str(e)}")
                return False

    async def search(self, query_str: str, page: int = 1):
        """执行搜索 (异步)"""
        api_url = f"{self.base_url}/api/v1/search/all"
        # Base64 编码查询语句
        qbase64 = base64.b64encode(query_str.encode('utf-8')).decode()

        params = {
            "email": self.email,
            "key": self.key,
            "qbase64": qbase64,
            "page": page,
            "size": settings.search.size,
            "fields": settings.search.fields,
            "full": str(settings.search.full).lower()
        }

        async with httpx.AsyncClient(http2=True) as client:
            try:
                logger.info(f"正在查询第 {page} 页...")
                resp = await client.get(api_url, params=params, headers=self.headers, timeout=30)
                result = resp.json()

                if result.get("error"):
                    logger.error(f"查询出错: {result.get('errmsg')}")
                    return []

                return result.get("results", [])
            except Exception as e:
                logger.error(f"查询请求异常: {str(e)}")
                return []