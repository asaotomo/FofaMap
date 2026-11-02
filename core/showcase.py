"""Built-in wizard examples whose FOFA queries were counted before they were published.

Each sentence is a representative task: geography, product fingerprint, time window,
statistics, a hard cap, a sample, a full small pull, or a host profile. The query is
fixed so the planner cannot replace it with an empty title or a rejected app name.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


def _month_start(today: date | None = None) -> str:
    current = today or date.today()
    return current.replace(day=1).isoformat()


def _week_start(today: date | None = None) -> str:
    current = today or date.today()
    return (current - timedelta(days=current.weekday())).isoformat()


_SEARCH_FIELDS = ("host", "ip", "port", "protocol", "title", "domain")

_PHP2SHELL_AFFECTED = (
    'app="php" && (product.version="8.2.0" || product.version="8.2.1" || product.version="8.2.2" || produ'
    'ct.version="8.2.3" || product.version="8.2.4" || product.version="8.2.5" || product.version="8.2.6" '
    '|| product.version="8.2.7" || product.version="8.2.8" || product.version="8.2.9" || product.version='
    '"8.2.10" || product.version="8.2.11" || product.version="8.2.12" || product.version="8.2.13" || prod'
    'uct.version="8.2.14" || product.version="8.2.15" || product.version="8.2.16" || product.version="8.2'
    '.17" || product.version="8.2.18" || product.version="8.2.19" || product.version="8.2.20" || product.'
    'version="8.2.21" || product.version="8.2.22" || product.version="8.2.23" || product.version="8.2.24"'
    ' || product.version="8.2.25" || product.version="8.2.26" || product.version="8.2.27" || product.vers'
    'ion="8.2.28" || product.version="8.2.29" || product.version="8.2.30" || product.version="8.2.31" || '
    'product.version="8.2.32" || product.version="8.2.33" || product.version="8.2.34" || product.version='
    '"8.3.0" || product.version="8.3.1" || product.version="8.3.2" || product.version="8.3.3" || product.'
    'version="8.3.4" || product.version="8.3.5" || product.version="8.3.6" || product.version="8.3.7" || '
    'product.version="8.3.8" || product.version="8.3.9" || product.version="8.3.10" || product.version="8'
    '.3.11" || product.version="8.3.12" || product.version="8.3.13" || product.version="8.3.14" || produc'
    't.version="8.3.15" || product.version="8.3.16" || product.version="8.3.17" || product.version="8.3.1'
    '8" || product.version="8.3.19" || product.version="8.3.20" || product.version="8.3.21" || product.ve'
    'rsion="8.3.22" || product.version="8.3.23" || product.version="8.3.24" || product.version="8.3.25" |'
    '| product.version="8.3.26" || product.version="8.3.27" || product.version="8.3.28" || product.versio'
    'n="8.3.29" || product.version="8.3.30" || product.version="8.3.31" || product.version="8.3.32" || pr'
    'oduct.version="8.3.33" || product.version="8.3.34" || product.version="8.3.35" || product.version="8'
    '.4.0" || product.version="8.4.1" || product.version="8.4.2" || product.version="8.4.3" || product.ve'
    'rsion="8.4.4" || product.version="8.4.5" || product.version="8.4.6" || product.version="8.4.7" || pr'
    'oduct.version="8.4.8" || product.version="8.4.9" || product.version="8.4.10" || product.version="8.4'
    '.11" || product.version="8.4.12" || product.version="8.4.13" || product.version="8.4.14" || product.'
    'version="8.4.15" || product.version="8.4.16" || product.version="8.4.17" || product.version="8.4.18"'
    ' || product.version="8.4.19" || product.version="8.4.20" || product.version="8.4.21" || product.vers'
    'ion="8.4.22" || product.version="8.4.23" || product.version="8.4.24" || product.version="8.4.25" || '
    'product.version="8.4.26" || product.version="8.5.0" || product.version="8.5.1" || product.version="8'
    '.5.2" || product.version="8.5.3" || product.version="8.5.4" || product.version="8.5.5" || product.ve'
    'rsion="8.5.6" || product.version="8.5.7" || product.version="8.5.8" || product.version="8.5.9" || pr'
    'oduct.version="8.5.10" || product.version="8.5.11")'
)



@dataclass(frozen=True)
class ShowcaseExample:
    prompt: str
    action: str
    query: str = ""
    purpose: str = ""
    stats_fields: tuple[str, ...] = ()
    fields: tuple[str, ...] = ()
    max_records: int | None = None
    page_size: int | None = None
    max_pages: int | None = None
    sample: bool = False
    target: str | None = None
    after: str | None = None

    def resolved_query(self, today: date | None = None) -> str:
        if not self.query:
            return ""
        if self.after == "month":
            return f'{self.query} && after="{_month_start(today)}"'
        if self.after == "week":
            return f'{self.query} && after="{_week_start(today)}"'
        return self.query

    def as_plan(self, today: date | None = None) -> dict[str, object]:
        query = self.resolved_query(today)
        queries = [{"query": query, "purpose": self.purpose, "strategy": "precision"}] if query else []
        return {
            "action": self.action,
            "target": self.target or "",
            "queries": queries,
            "stats_fields": list(self.stats_fields),
            "fields": list(self.fields),
            "scan": {
                "recommended": False,
                "reason": "内置样例只做检索、统计或主机画像，不主动扫描。",
                "template_ids": [],
                "severities": [],
            },
        }


_VPN = (
    '(app="SANGFOR-SSL-VPN" || app="奇安信-VPN" || app="FORTINET-SSLVPN" || app="天融信-VPN")'
    ' && city="Beijing"'
)
_OA = 'city="Nanjing" && (app="致远互联-OA" || app="泛微-协同办公OA")'

SHOWCASES: tuple[ShowcaseExample, ...] = (
    ShowcaseExample(
        "查找上海本月有更新的 Grafana，统计端口",
        "stat_query",
        'app="Grafana" && city="Shanghai" && country="CN"',
        "上海本月有更新的 Grafana，按端口聚合",
        ("port",),
        after="month",
    ),
    ShowcaseExample(
        "收集北京大学的子域名网站，只要前 100 条，不要扫描",
        "fofa_search",
        'domain="pku.edu.cn"',
        "北京大学域名下的网站",
        fields=_SEARCH_FIELDS,
        max_records=100,
        page_size=100,
        max_pages=1,
    ),
    ShowcaseExample(
        "统计中国境内暴露的 Redis，按端口和协议汇总",
        "stat_query",
        'app="Redis" && country="CN"',
        "中国境内 Redis 的端口和协议",
        ("port", "protocol"),
    ),
    ShowcaseExample(
        "查找深圳市使用 Nginx 的网站，只要前 100 条",
        "fofa_search",
        'app="Nginx" && city="Shenzhen" && country="CN"',
        "深圳市 Nginx 网站，最多 100 条",
        fields=_SEARCH_FIELDS,
        max_records=100,
        page_size=100,
        max_pages=1,
    ),
    ShowcaseExample(
        "统计广东省 Apache 网站的操作系统分布",
        "stat_query",
        'app="APACHE-HTTP_Server" && region="广东"',
        "广东省 Apache 的操作系统",
        ("os",),
    ),
    ShowcaseExample(
        "查找东京的 Jenkins，统计协议分布",
        "stat_query",
        'app="Jenkins" && city="Tokyo"',
        "东京 Jenkins 的协议",
        ("protocol",),
    ),
    ShowcaseExample(
        "查找杭州市 gov.cn 网站，统计端口",
        "stat_query",
        'city="Hangzhou" && host=".gov.cn"',
        "杭州市政府域名的端口",
        ("port",),
    ),
    ShowcaseExample(
        "查找北京市本月有更新的 VPN 设备，统计端口",
        "stat_query",
        _VPN,
        "北京市本月有更新的 VPN 设备端口",
        ("port",),
        after="month",
    ),
    ShowcaseExample(
        "查找成都市的海康威视设备，导出前 300 条，每页 100 条",
        "fofa_search",
        'city="Chengdu" && app="HIKVISION-视频监控"',
        "成都市海康威视设备，每页 100 条，最多 300 条",
        fields=_SEARCH_FIELDS,
        max_records=300,
        page_size=100,
        max_pages=3,
    ),
    ShowcaseExample(
        "收集清华大学的子域名网站，只要前 100 条",
        "fofa_search",
        'domain="tsinghua.edu.cn"',
        "清华大学域名下的网站",
        fields=_SEARCH_FIELDS,
        max_records=100,
        page_size=100,
        max_pages=1,
    ),
    ShowcaseExample(
        "查找新加坡的 GitLab，统计端口",
        "stat_query",
        'app="GitLab" && country="SG"',
        "新加坡 GitLab 的端口",
        ("port",),
    ),
    ShowcaseExample(
        "抽样查看中国境内 Elasticsearch 的标题，只要 30 条",
        "fofa_search",
        'app="Elasticsearch" && country="CN"',
        "中国境内 Elasticsearch 标题抽样",
        fields=_SEARCH_FIELDS,
        max_records=30,
        page_size=30,
        max_pages=1,
        sample=True,
    ),
    ShowcaseExample(
        "统计上海市 ThinkPHP 网站的标题和端口",
        "stat_query",
        'app="ThinkPHP" && city="Shanghai" && country="CN"',
        "上海市 ThinkPHP 的标题和端口",
        ("title", "port"),
    ),
    ShowcaseExample(
        "收集香港的 Fortinet 设备，只要前 100 条",
        "fofa_search",
        'app="FORTINET-防火墙" && country="HK"',
        "香港 Fortinet 设备",
        fields=_SEARCH_FIELDS,
        max_records=100,
        page_size=100,
        max_pages=1,
    ),
    ShowcaseExample(
        "查找中国境内本周有更新的 Confluence，统计端口",
        "stat_query",
        'app="Atlassian-Confluence" && country="CN"',
        "中国境内本周更新的 Confluence 端口",
        ("port",),
        after="week",
    ),
    ShowcaseExample(
        "统计美国 .edu 网站的标题分布",
        "stat_query",
        'country="US" && host=".edu"',
        "美国 .edu 后缀网站的标题",
        ("title",),
    ),
    ShowcaseExample(
        "查找广州市的海康威视设备，统计端口",
        "stat_query",
        'app="HIKVISION-视频监控" && city="Guangzhou"',
        "广州市海康威视设备的端口",
        ("port",),
    ),
    ShowcaseExample(
        "查找南京市的致远和泛微 OA，只要前 100 条",
        "fofa_search",
        _OA,
        "南京市致远与泛微 OA",
        fields=(*_SEARCH_FIELDS, "product"),
        max_records=100,
        page_size=100,
        max_pages=1,
    ),
    ShowcaseExample(
        "查找上海市的 Harbor 镜像仓库，统计端口",
        "stat_query",
        'app="Harbor" && city="Shanghai"',
        "上海市 Harbor 的端口",
        ("port",),
    ),
    ShowcaseExample(
        "统计浙江省 WebLogic 的端口和协议",
        "stat_query",
        'app="BEA-WebLogic-Server" && region="浙江"',
        "浙江省 WebLogic 的端口和协议",
        ("port", "protocol"),
    ),
    ShowcaseExample(
        "查找重庆市的 Zabbix，做全量检索",
        "fofa_search",
        'app="ZABBIX-监控系统" && city="Chongqing"',
        "重庆市 Zabbix 全量结果",
        fields=_SEARCH_FIELDS,
        max_records=500,
        page_size=100,
        max_pages=5,
    ),
    ShowcaseExample(
        "收集微软的子域名网站，只要前 100 条，不要扫描",
        "fofa_search",
        'domain="microsoft.com"',
        "微软域名下的网站",
        fields=_SEARCH_FIELDS,
        max_records=100,
        page_size=100,
        max_pages=1,
    ),
    ShowcaseExample(
        "查找山西省的锐捷设备，统计端口",
        "stat_query",
        'region="山西" && app="Ruijie"',
        "山西省锐捷设备的端口",
        ("port",),
    ),
    ShowcaseExample(
        "收集哈佛大学的子域名网站，只要前 100 条，不要扫描",
        "fofa_search",
        'domain="harvard.edu"',
        "哈佛大学域名下的网站",
        fields=_SEARCH_FIELDS,
        max_records=100,
        page_size=100,
        max_pages=1,
    ),
    ShowcaseExample(
        "查看 8.8.8.8 的主机画像",
        "host_query",
        purpose="8.8.8.8 的主机聚合画像",
        target="8.8.8.8",
    ),
    ShowcaseExample(
        "查询最新的 php2shell 漏洞资产，统计端口",
        "stat_query",
        _PHP2SHELL_AFFECTED,
        "PHP2Shell 受影响版本的端口。版本号只说明暴露面，不能判定漏洞。",
        ("port",),
    ),
)

SHOWCASE_PROMPTS: tuple[str, ...] = tuple(item.prompt for item in SHOWCASES)
_BY_PROMPT = {item.prompt: item for item in SHOWCASES}


def showcase_for(intent: str) -> ShowcaseExample | None:
    return _BY_PROMPT.get(intent.strip())
