import asyncio
import aiohttp


class FastCheck:
    def __init__(self, aim_urls, timeout=5):
        self.urls = aim_urls
        self.result_dict = {}
        self.timeout = timeout

    async def check_url(self, url):
        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False)) as session:
                response = await asyncio.wait_for(session.get(url), timeout=self.timeout)
                try:
                    if response.status == 200:
                        self.result_dict[url] = "200"
                    else:
                        self.result_dict[url] = "{}".format(response.status)
                finally:
                    await response.release()
        except asyncio.TimeoutError:
            self.result_dict[url] = "Timeout exceeds {}s".format(self.timeout)
        except aiohttp.ClientError as e:
            self.result_dict[url] = "Unknown error"

    async def check_urls(self):
        tasks = []
        for url in self.urls:
            task = asyncio.ensure_future(self.check_url(url.rstrip("\n")))
            tasks.append(task)
        await asyncio.gather(*tasks)
