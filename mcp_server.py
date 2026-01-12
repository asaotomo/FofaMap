import sys
import os
import builtins
import logging
import datetime
from pathlib import Path

# ==============================================================================
# 🛡️ MCP 协议防污染补丁（必须最早执行）
# ==============================================================================

_original_print = builtins.print


def mcp_safe_print(*args, **kwargs):
    kwargs['file'] = sys.stderr
    _original_print(*args, **kwargs)


builtins.print = mcp_safe_print


def setup_global_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='[MCP-LOG] %(message)s',
        stream=sys.stderr,
        force=True
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


setup_global_logging()

# ==============================================================================
# 环境初始化 & 依赖注入
# ==============================================================================

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

try:
    from mcp.server.fastmcp import FastMCP
    from core.client import FofaClient
    from core.ai import DeepSeekHandler
    from utils.helpers import IconHashCalculator, FastChecker
    from config import settings
    from utils.logger import logger as app_logger
except ImportError as e:
    sys.stderr.write(f"❌ 依赖导入失败: {e}\n")
    sys.exit(1)


# ==============================================================================
# 🛡️ 二次保险：覆盖业务 Logger 输出到 stderr
# ==============================================================================

def mcp_safe_log(msg):
    sys.stderr.write(f"[MCP-LOG] {str(msg)}\n")
    sys.stderr.flush()


app_logger.info = mcp_safe_log
app_logger.error = mcp_safe_log
app_logger.warning = mcp_safe_log
app_logger.ai = mcp_safe_log

# ==============================================================================
# MCP 实例
# ==============================================================================

mcp = FastMCP("Fofamap-Platinum-Full-Expert")


# ==============================================================================
# Markdown 表格工具
# ==============================================================================

def format_table(headers: list, rows: list, max_rows: int = 25) -> str:
    if not rows:
        return "> ⚠️ 无数据。"

    def clean(cell):
        s = str(cell).replace("|", "\\|").replace("\n", " ").strip()
        return (s[:47] + "...") if len(s) > 50 else s

    md = "| " + " | ".join(headers) + " |\n"
    md += "| " + " | ".join(["---"] * len(headers)) + " |\n"

    for i, row in enumerate(rows):
        if i >= max_rows:
            break
        current_row = list(row) + ["-"] * (len(headers) - len(row))
        md += "| " + " | ".join([clean(c) for c in current_row]) + " |\n"

    if len(rows) > max_rows:
        md += f"\n\n> *ℹ️ 共 {len(rows)} 条，仅显示前 {max_rows} 条*"

    return md


# ==============================================================================
# MCP 工具 1：FOFAMAP 搜索
# ==============================================================================

@mcp.tool()
async def search_assets(query: str, fields: str = None,
                        pages: int = 1, full: bool = False):
    """
    [1. 资产检索] 执行 FOFA 查询。

    📚 字段指南:
    - Leve 0+ (全员可用): ip, port, protocol, host, domain, title, server, country, city, org, asn
    - Level 11+ or Level 2+ (个人版及以上、高级会员(专业版)可用): header_hash, banner_hash, banner_fid
    - Level 12+（专业版及以上，企业会员level 5可用）: product, product_category, cname, cert, cert.subject.cn
    - Level 13+（商业版本及以上，企业会员level 5可用）: body, icon_hash, fid
    - Level 5（企业会员专享）: icon, structinfo

    ⚠️ AI 专家语法战法:
    - 组合拳: (app="xxx" || app="yyy") && country="CN" 
      示例: `(app="致远互联-OA" || app="用友-NC-Cloud") && region="Beijing"`
    - 精准字段:
       - 查数据库 -> `protocol="mysql"` (不要用 product)
       - 查后台/登录 -> `title="后台管理" || body="login"`
       - 查证书/组织 -> `cert="google" || cert.subject.org="Google"`
    - 地理位置: 必须使用拼音！
       - ❌ 错误: `city="上海"`
       - ✅ 正确: `city="Shanghai"`, `region="Zhejiang"`

    Args:
        query: FOFA 查询语法 (例如: `app="ThinkPHP" && country="CN"`)
        fields: [可选] 逗号分隔的返回字段。默认为基础资产字段。若需查证书或正文，请在此显式添加 (如 "host,ip,cert,body")。
        pages: 查询页数 (默认 1)
        full: 是否搜索历史数据 (默认 False)
    """

    settings.search.full = full
    client = FofaClient()
    # 2. 【新增】主动获取用户等级
    try:
        user_info = await client.check_login()
        vip_level = user_info.get("vip_level", 0)
    except:
        vip_level = 0

    # 3. 【新增】根据等级动态计算默认字段
    # 基础字段
    allowed_defaults = [
        "host", "ip", "port", "protocol",
        "title", "server",
        "domain", "country_name"
    ]

    # 只有 Level 12+ 或 Level 2(旧) 才能加 product 和 lastupdatetime
    if vip_level >= 12 or vip_level == 2 or vip_level == 5:
        allowed_defaults.extend(["product", "lastupdatetime"])

    if not fields:
        target_fields = ",".join(allowed_defaults)
    else:
        target_fields = fields

    try:
        results, effective_fields = await client.search(query, page=pages, fields=target_fields)
    except Exception as e:
        return f"❌ FOFA 请求异常: {str(e)}"

    if not results:
        return f"🔍 未发现资产，实际查询字段: `{effective_fields}`"

    formatted_results = [r if isinstance(r, list) else [r] for r in results]
    header_list = [f.strip().capitalize() for f in target_fields.split(",")]
    clean_headers = [h[:10] for h in header_list]

    return f"### 🔍 FOFA 检索结果: `{query}`\n" + format_table(clean_headers, formatted_results)


# ==============================================================================
# MCP 工具 2：Host 聚合画像
# ==============================================================================

@mcp.tool()
async def get_host_aggregation(host: str):
    """[2. Host精准画像] 获取单个目标(IP/域名)的聚合详情，含端口、ASN及地理位置。"""
    client = FofaClient()

    try:
        data = await client.host_search(host)
    except Exception as e:
        return f"❌ 查询异常: {e}"

    if not data or data.get("error"):
        return f"❌ 查询失败: {data.get('errmsg', '目标不存在')}"

    res = [
        f"### 🖥️ Host 画像: {data.get('host', host)}",
        f"- **基本信息**: `{data.get('ip')}` | {data.get('country_name')} | {data.get('org')}",
        f"- **ASN**: {data.get('asn')} | **更新时间**: {data.get('update_time')}"
    ]

    ports_data = data.get('ports', [])
    if ports_data:
        ports_data.sort(key=lambda x: x.get('port', 0))
        rows = [
            [p.get('port'), p.get('protocol', '-'),
             ", ".join([x.get('product', '') for x in p.get('products', [])])]
            for p in ports_data
        ]
        res.append("\n#### 🔌 开放端口与指纹\n" + format_table(["Port", "Protocol", "Products"], rows))

    return "\n".join(res)


# ==============================================================================
# MCP 工具 3：统计聚合
# ==============================================================================

@mcp.tool()
async def get_stats_aggregation(query: str, fields: str = "country,title,org"):
    """[3. 统计聚合] 统计资产分布，支持针对全球各地区的资产分布统计。
        - 支持的字段如下 (仅限这些): `protocol`, `domain`, `port`, `title`, `os`, `server`, `country`, `asn`, `org`, `asset_type`, `fid`, `icp`
        - *示例1*: 用户查 "端口分布" -> fields="port"; 用户查 "国家排名" -> fields="country"。
        - *示列2*: 用户查 "redis在中国的分布情况" —> app="redis" && country="CN" fields="country,port,org,asn"。
    """
    client = FofaClient()

    try:
        data = await client.stats_search(query, fields)
    except Exception as e:
        return f"❌ 统计异常: {e}"

    if not data:
        return "⚠️ 无统计数据。"

    summary = f"### 📊 资产统计分布 (总量: {data.get('size', 0)})\n"
    aggs = data.get("aggs", {})

    for field, items in aggs.items():
        if not items:
            continue
        summary += f"\n#### 🏆 {field.upper()} Top 10\n"
        summary += format_table(["名称", "数量"], [[i.get('name'), str(i.get('count'))] for i in items[:10]])

    return summary


# ==============================================================================
# MCP 工具 4：Icon Hash 计算
# ==============================================================================

@mcp.tool()
async def calculate_icon_hash(url: str):
    """[4. 图标 Hash] 提取目标网站 Favicon 并计算 icon_hash。"""
    try:
        hash_query = await IconHashCalculator.get_hash(url)
        if hash_query:
            return f"✅ 计算成功！\n请使用: `{hash_query}`"
        return "❌ 获取 favicon 失败。"
    except Exception as e:
        return f"❌ 异常: {e}"


# ==============================================================================
# MCP 工具 5：FOFAMAP AI 军师
# ==============================================================================

@mcp.tool()
async def ai_security_consultant(user_intent: str):
    """
    [5. AI 参谋] 基于 AI 专家大脑制定战术方案。

    ⚠️ AI 决策逻辑:
    - 拼音优先: 自动将“上海”转换为 "Shanghai"。
    - 权限感知: 严格受 VIP 等级限制选择字段。
    - 智能选择查询命令参数:
        - **网络层**: `ip`, `port`, `protocol`, `base_protocol`
        - **域名/主机**: `host`, `domain`, `link`
        - **基础指纹**: `title`, `server`, `os`, `header`, `banner`, `icp`, `jarm`
        - **地理位置**: `country`, `country_name`, `region`, `city`, `longitude`, `latitude`, `asn`, `org`
        - **证书基础**: `cert`, `cert.domain`, `cert.sn`
        - **证书详情**: `cert.issuer.org`, `cert.issuer.cn`, `cert.subject.org`, `cert.subject.cn`
        - **TLS信息**: `tls.ja3s`, `tls.version`, `cert.not_before`, `cert.not_after`
        - **Hash/Fid**: `header_hash`, `banner_hash`, `banner_fid`
        - **关键增强**: `product` (产品名), `product_category` (分类), `cname`, `lastupdatetime`
        - **高危字段**: **`body`** (网页正文), `icon_hash`, `fid` (聚合指纹), `icon`, `structinfo`
        - **深度验证**: `product.version`, `cert.is_valid`, `cname_domain`, `cert.is_match`, `cert.is_equal`
    """
    ai_handler = DeepSeekHandler()
    client = FofaClient()

    try:
        user_info = await client.check_login()
    except:
        user_info = {"vip_level": 1}

    plan = await ai_handler.strategic_planning(user_intent, user_info or {"vip_level": 1})
    if not plan:
        return "⚠️ AI 思考失败。"

    return (
        "### 🧠 AI 专家战术规划\n"
        f"- **推荐查询语句**: `{plan.get('queries')}`\n"
        f"- **动作路由**: `{plan.get('action')}`\n"
        f"- **扫描决策**: {'✅ 建议开启' if plan.get('run_nuclei') else '❌ 不建议执行'}"
    )


# ==============================================================================
# MCP 工具 6：网站存活检测
# ==============================================================================

@mcp.tool()
async def check_assets_alive(hosts: list[str]):
    """[6. 存活检测] HTTP/HTTPS 网站存活检测。"""
    try:
        results = await FastChecker.check_alive(hosts, timeout=5)
        alive_data = [[url, str(code)] for url, code in results.items() if str(code).isdigit()]
        return f"### 🟢 存活资产 ({len(alive_data)}/{len(hosts)})\n" + format_table(["URL", "状态码"], alive_data)
    except Exception as e:
        return f"❌ 检测异常: {e}"


# ==============================================================================
# MCP 工具 7：生成 Nuclei 扫描命令
# ==============================================================================

@mcp.tool()
async def generate_nuclei_command(targets: list[str], severity: str = "medium,high,critical"):
    """
    [7. 扫描指令生成] 仅生成命令，不在 MCP 中执行。

    【决策逻辑 (CoT)】
        1. **技术栈识别**: 分析样本中的 Title/Server/Header/Port。
           - 发现 `Java/Spring/Shiro` -> 推荐 `-tags spring,shiro,java` 或 `-t cves/202x/Java`。
           - 发现 `ThinkPHP/Laravel` -> 推荐 `-tags thinkphp,laravel`。
           - 发现 `WebLogic/JBoss` -> 推荐 `-tags weblogic,jboss`。
           - 发现 `Exchange/OA` -> 推荐 `-tags exchange,oa`。
        2. **意图对齐**:
           - 若用户查特定漏洞 (如 "Log4j") -> 必须包含 `-tags log4j` 或 `-id CVE-2021-44228`。
           - 若用户做大范围普查 -> 推荐 `-as` (自动指纹识别) 配合 `-severity critical,high`。
        3. **参数调优**:
           - 目标少且重要 -> 加上 `-bs 25 -rl 150` (提升速率)。
           - 目标多且杂 -> 加上 `-tags cves,misconfig` (通用扫描)。
    """

    if not targets:
        return "❌ 目标列表为空。"

    targets_text = "\n".join(targets)

    cmd = (
        "nuclei -l targets.txt "
        f"-severity {severity} "
        "-stats "
        "-o result.txt"
    )

    return (
        "### ☢️ Nuclei 扫描任务建议\n\n"
        "#### 📄 targets.txt 内容：\n"
        f"```text\n{targets_text}\n```\n\n"
        "#### ▶️ 请在扫描节点 / 本地终端执行：\n"
        "```bash\n"
        "# 1. 保存 targets\n"
        "cat > targets.txt << 'EOF'\n"
        f"{targets_text}\n"
        "EOF\n\n"
        "# 2. 执行扫描\n"
        f"{cmd}\n"
        "```"
    )


# ==============================================================================
# 入口
# ==============================================================================

if __name__ == "__main__":
    mcp.run()
