import asyncio
import random
import aiohttp


class FastCheck:
    def __init__(self, aim_urls, timeout=5):
        self.urls = aim_urls
        self.result_dict = {}
        self.timeout = timeout
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.3',
            'Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; AS; rv:11.0) like Gecko',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3282.140 Safari/537.3',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/113.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5026.0 Safari/537.36 Edg/103.0.1253.0',
            'Mozilla/4.0 (compatible; MSIE 6.0; Linux 2.6.26-1-amd64) Lobo/0.98.3',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 15_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/98.0.4758.85 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (Linux; Android 13; SM-A037U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36 uacq']

    async def check_url(self, url):
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False)) as session:
            headers = {'User-Agent': random.choice(self.user_agents)}
            try:
                async with session.get(url, headers=headers, timeout=self.timeout) as response:
                    if response.status == 200:
                        self.result_dict[url] = "200"
                    else:
                        self.result_dict[url] = "{}".format(response.status)
            except asyncio.TimeoutError:
                self.result_dict[url] = "Timeout exceeds {}s".format(self.timeout)
            except aiohttp.ClientError as e:
                self.result_dict[url] = "Unknown error"

        return self.result_dict[url]

    async def check_urls(self):
        tasks = []
        for url in self.urls:
            task = asyncio.ensure_future(self.check_url(url))
            tasks.append(task)
        return await asyncio.gather(*tasks)
