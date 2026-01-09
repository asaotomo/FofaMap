import mmh3
import codecs
import httpx
import asyncio
from urllib.parse import urlparse
from utils.logger import logger


class IconHashCalculator:
    @staticmethod
    async def get_hash(url: str) -> str:
        """计算 favicon hash"""
        if not url.startswith("http"):
            url = f"http://{url}"

        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        favicon_url = f"{base_url}/favicon.ico"

        # 使用 httpx 异步客户端下载图标
        async with httpx.AsyncClient(verify=False, timeout=10) as client:
            try:
                logger.info(f"正在下载图标: {favicon_url}")
                resp = await client.get(favicon_url)
                if resp.status_code == 200:
                    favicon = resp.content
                    # 标准 FOFA Icon Hash 计算逻辑
                    icon_hash = mmh3.hash(codecs.lookup('base64').encode(favicon)[0])
                    return f'icon_hash="{icon_hash}"'
                else:
                    return None
            except Exception as e:
                logger.warning(f"图标计算失败: {e}")
                return None


class FastChecker:
    @staticmethod
    async def check_alive(targets: list, timeout: int = 5) -> dict:
        """
        批量存活检测
        返回: {url: status_code_or_msg}
        """
        results = {}
        # 对目标进行去重处理
        targets = list(set(targets))

        # 限制并发量，防止在大规模扫描时耗尽系统句柄 (Semaphore)
        sem = asyncio.Semaphore(50)  # 限制最大50个并发任务

        async with httpx.AsyncClient(verify=False, timeout=timeout) as client:
            tasks = []
            for target in targets:
                url = target if target.startswith("http") else f"http://{target}"
                tasks.append(FastChecker._fetch(client, url, sem))

            # 并发执行所有检测任务
            responses = await asyncio.gather(*tasks)
            for url, code in responses:
                results[url] = code
        return results

    @staticmethod
    async def _fetch(client, url, sem):
        """执行单个 URL 的获取任务"""
        async with sem:
            try:
                resp = await client.get(url)
                return url, resp.status_code
            except httpx.TimeoutException:
                return url, "Timeout"  # 超时处理
            except httpx.ConnectError:
                return url, "ConnErr"  # 连接错误处理
            except Exception as e:
                # 其他未知错误
                return url, "Error"
