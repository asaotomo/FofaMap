import asyncio
import os
import subprocess
import yaml
import rich_click as click
import questionary
from colorama import init, Fore, Style
from pathlib import Path

# 导入配置和工具
from config import settings
from utils.logger import logger
from utils.printer import ResultPrinter, print_header, print_item, print_config, print_userinfo
from utils.helpers import IconHashCalculator
# 导入核心处理器
from core.handler import FofaHandler
from core.scanner import NucleiScanner

init(autoreset=True)

# Rich-click 样式配置
click.rich_click.USE_RICH_MARKUP = True
click.rich_click.OPTION_GROUPS = {
    "fofamap.py": [
        {"name": "🔮 核心查询功能 (Core Queries)",
         "options": ["--ai_query", "--query", "--host_query", "--icon_query", "--count_query", "--bat_query"]},
        {"name": "⚙️ 过滤与配置 (Filter & Config)",
         "options": ["--query_fields", "--pages", "--key_word", "--include"]},
        {"name": "🚀 扫描与输出 (Scan & Output)",
         "options": ["--batch", "--nuclei", "--update", "--outfile", "--outdir", "--export-format"]},
    ]
}


def print_banner():
    print(Fore.CYAN + r"""
    ________      ____        __  ___            
   / ____/ /_  __/ __/___ _  /  |/  /___ _____   
  / /_  / __ \/ / /_/ __ `/ / /|_/ / __ `/ __ \  
 / __/ / /_/ / / __/ /_/ / / /  / / /_/ / /_/ /  
/_/    \____/_/_/  \__,_/ /_/  /_/\__,_/ .___/   
                                      /_/   v2.0 
    [ AI Powered & Interactive Wizard ] -- By Hx0 Team 2026.03.26
    """ + Style.RESET_ALL)


def init_config():
    """ [全量初始化] 增加类型强制转换保护 + 补全 AI 高级配置 """
    print_header("FofaMap 环境初始化")
    config_path = Path("config/settings.yaml")

    current = {}
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                current = yaml.safe_load(f) or {}
        except:
            pass

    print(Fore.YELLOW + "[*] 请按照提示输入配置信息 (直接回车保持默认值):" + Style.RESET_ALL)

    # 1. 基础账号凭证
    email = str(questionary.text("FOFA 账号 Email:", default=current.get('userinfo', {}).get('email', '')).ask())
    key = str(questionary.password("FOFA API Key:", default=current.get('userinfo', {}).get('key', '')).ask())
    ds_key = str(questionary.password("DeepSeek API Key (AI 模式必需):",
                                      default=current.get('userinfo', {}).get('deepseek_api_key', '')).ask())

    # === [新增] 2. AI 高级配置 (补全逻辑) ===
    api_type = questionary.select(
        "AI 接口类型 (API Type):",
        choices=["deepseek", "openai", "ollama", "lmstudio"],
        default=current.get('userinfo', {}).get('api_type', 'deepseek')
    ).ask()

    # 根据类型提供智能的默认 BaseURL
    default_base_url = "https://api.deepseek.com/v1"
    if api_type == "ollama":
        default_base_url = "http://localhost:11434/v1"
    elif api_type == "lmstudio":
        default_base_url = "http://localhost:1234/v1"

    base_url = questionary.text(
        "AI API Base URL:",
        default=current.get('userinfo', {}).get('base_url', default_base_url)
    ).ask()

    model = questionary.text(
        "模型名称 (Model Name):",
        default=current.get('userinfo', {}).get('model', 'deepseek-chat')
    ).ask()
    # ========================================

    # 3. 默认搜索设置
    fields = questionary.text("默认查询字段 (Fields):", default=current.get('search', {}).get('fields',
                                                                                              'host,protocol,ip,port,title,domain,country')).ask()
    size = int(
        questionary.text("单页获取数量 (Size, 最大 10000):", default=str(current.get('search', {}).get('size', 100)),
                         validate=lambda t: t.isdigit()).ask())
    full = questionary.confirm("是否默认搜索全部历史数据 (Full):",
                               default=current.get('search', {}).get('full', False)).ask()
    end_page = int(
        questionary.text("默认查询结束页数 (End Page):", default=str(current.get('search', {}).get('end_page', 2)),
                         validate=lambda t: t.isdigit()).ask())

    # 4. 性能与检测
    alive = questionary.confirm("是否开启存活检测 (Check Alive):",
                                default=current.get('fast_check', {}).get('check_alive', True)).ask()
    timeout = int(
        questionary.text("存活检测超时时间 (秒):", default=str(current.get('fast_check', {}).get('timeout', 5)),
                         validate=lambda t: t.isdigit()).ask())
    concurrency = int(
        questionary.text("异步并发数 (Concurrency):", default=str(current.get('system', {}).get('concurrency', 10)),
                         validate=lambda t: t.isdigit()).ask())

    merge = questionary.confirm("是否合并批量查询结果到单个导出文件:",
                                default=current.get('system', {}).get('sheet_merge', True)).ask()
    export_format = questionary.select(
        "默认导出格式 (Export Format):",
        choices=["xlsx", "csv"],
        default=current.get('system', {}).get('export_format', 'xlsx')
    ).ask()
    output_dir = questionary.text(
        "默认导出目录 (Output Directory):",
        default=current.get('system', {}).get('output_dir', 'results')
    ).ask()

    new_config = {
        'userinfo': {
            'email': email,
            'key': key,
            'deepseek_api_key': ds_key,
            # [新增] 写入配置
            'api_type': api_type,
            'base_url': base_url,
            'model': model
        },
        'search': {
            'fields': fields,
            'size': size,
            'full': full,
            'start_page': 1,
            'end_page': end_page
        },
        'fast_check': {'check_alive': alive, 'timeout': timeout},
        'system': {
            'logger': True,
            'sheet_merge': merge,
            'concurrency': concurrency,
            'export_format': export_format,
            'output_dir': output_dir or 'results'
        }
    }

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(new_config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    logger.info("🎉 配置文件初始化完成。")


def run_interactive_wizard():
    """ 启动交互式向导 (含退出选项与示例引导) """
    print(Fore.YELLOW + "\n[!] 启动任务向导..." + Style.RESET_ALL)

    mode = questionary.select(
        "请选择您要执行的操作:",
        choices=[
            "1. 🔮 AI 智能侦察 (自然语言 -> 自动决策)",
            "2. 🔍 FOFA 标准查询 (语法输入)",
            "3. 🖥️ Host 聚合查询 (IP/域名详情)",
            "4. 📊 统计聚合查询 (数据分布分析)",
            "5. 🖼️ Icon Hash 查询 (favicon 逆向)",
            "6. 📁 批量文件查询 (TXT 批量指令)",
            questionary.Separator(),
            "0. 🚪 退出程序"
        ]
    ).ask()

    if not mode or "退出程序" in mode:
        return None

    args = {}
    if "AI" in mode:
        args['ai_query'] = questionary.text("请输入您的安全需求:",
                                            instruction=" (例如: '帮我收集一下XX学校的子域名网站，并扫描一下' 或 '统计全球Redis端口分布' 或 '分析 8.8.8.8')").ask()
    elif "标准查询" in mode:
        args['query'] = questionary.text("请输入 FOFA 语法:", instruction=" (例如: app=\"HIKVISION-视频监控\")").ask()
    elif "Host 聚合" in mode:
        args['host_query'] = questionary.text("请输入目标 IP 或 域名:", instruction=" (例如: 8.8.8.8)").ask()
        return args
    elif "统计聚合" in mode:
        args['count_query'] = questionary.text("请输入统计语法:", instruction=" (例如: app=\"Redis\")").ask()
        args['query_fields'] = questionary.text("统计字段 (可选):", default="title,port,country",
                                                instruction=" (默认为 title,port,country)").ask()
        return args
    elif "Icon Hash" in mode:
        args['icon_query'] = questionary.text("请输入目标 URL:",
                                              instruction=" (程序将自动提取并计算 favicon Hash)").ask()
    elif "批量文件" in mode:
        args['bat_query'] = questionary.path("请选择 TXT 文件路径:").ask()

    # 询问页数 (Icon Hash 和 批量文件等模式不再遗漏)
    args['pages'] = int(questionary.text("查询深度 (页数):", default="1", validate=lambda t: t.isdigit()).ask())

    if not args.get('ai_query'):
        if questionary.confirm("🚀 是否同步开启 Nuclei 漏洞扫描?", default=False).ask():
            args['nuclei'] = True

    return args


@click.command()
@click.argument("cmd", required=False)
@click.option("-ai", "--ai_query", help="🤖 [AI模式] 一句话，AI帮你执行任务")
@click.option("-q", "--query", help="🔍 [标准模式] 输入 FOFA 查询语法 (如 'app=\"nginx\" && port=\"8080\"')")
@click.option("-hq", "--host_query", help="🖥️ [Host画像] 查询单个 IP 或域名的聚合详情(如 8.8.8.8 或 baidu.com)")
@click.option("-cq", "--count_query", help="📊 [统计聚合] 查询全球资产分布统计 (如 'app=\"redis\" && country=\"US\"')")
@click.option("-ico", "--icon_query", help="🖼️ [图标查询] 输入网站 URL ，查询全网相似网站图标资产")
@click.option("-bq", "--bat_query", help="📂 [批量模式] 指定包含查询语法的 TXT 文件路径")
@click.option("-f", "--query_fields", help="⚙️ [字段配置] 自定义返回字段 (默认为配置文件设置)")
@click.option("-p", "--pages", default=0, help="📄 [页数设置] 指定查询页数 (0 为使用配置文件默认值)")
@click.option("-k", "--key_word", help="🔍 [本地筛选] 在结果中进一步搜索特定关键词")
@click.option("-i", "--include", help="➕ [包含模式] 只保留包含特定字符串的结果")
@click.option("-n", "--nuclei", is_flag=True, help="☢️ [漏洞扫描] 检索结束后自动调用 Nuclei 进行扫描")
@click.option("-batch", "--batch", is_flag=True, help="🚀 [无人值守] 自动确认所有提示 (适合AI模式)")
@click.option("-up", "--update", is_flag=True, help="🔄 [Nuclei更新] 检查并更新 Nuclei 版本")
@click.option("-o", "--outfile", help="💾 [结果输出] 自定义结果文件名（可带路径）")
@click.option("--outdir", help="📁 [导出路径] 自定义结果输出目录")
@click.option(
    "--export-format",
    "export_format",
    type=click.Choice(["xlsx", "csv"], case_sensitive=False),
    help="📦 [导出格式] 选择结果导出格式（xlsx/csv）"
)
def main(cmd, **kwargs):
    print_banner()

    if cmd == "init":
        init_config()
        return

    if kwargs['update']:
        temp_scanner = NucleiScanner()
        bin_path = temp_scanner.nuclei_path
        if bin_path:
            subprocess.run([bin_path, "-update"], check=False)
            subprocess.run([bin_path, "-ut"], check=False)
        return

    params_set = [kwargs['query'], kwargs['host_query'], kwargs['bat_query'], kwargs['ai_query'], kwargs['icon_query'],
                  kwargs['count_query']]
    if not any(params_set) and not cmd:
        wizard_args = run_interactive_wizard()
        if wizard_args:
            kwargs.update(wizard_args)
        else:
            return

    if kwargs['pages'] == 0:
        kwargs['pages'] = settings.search.end_page

    asyncio.run(run_async(**kwargs))


async def run_async(**kwargs):
    handler = FofaHandler()
    user_info = await handler.init_user()
    if not user_info: return
    print_userinfo(user_info)

    candidate_queries = []
    final_scan_args = ""
    ai_query_str = kwargs.get('ai_query')

    # --- [核心逻辑: AI 智能路由分发 (v2.0)] ---
    if ai_query_str:
        plan = await handler.ai_handler.strategic_planning(ai_query_str, user_info)
        if plan:
            action = plan.get("action", "fofa_search")
            target = plan.get("target")
            queries = plan.get("queries", [])
            fields = plan.get("fields", "")

            # 1. [Host 单体画像] AI 决定查看 IP 详情
            if action == "host_query":
                # 容错：如果 AI 没填 target 但查询语句里有 IP，尝试提取
                if not target and queries:
                    target = queries[0]

                if target:
                    # [修复] 强力清洗 target，去除可能存在的引号、空格、换行符
                    target = str(target).strip().strip("'").strip('"').strip()
                    logger.ai(f"AI 智能体路由决策: [Host 单体画像] -> {target}")
                    await handler.handle_host_query(target, user_intent=ai_query_str, outdir=kwargs.get('outdir'))
                else:
                    logger.error("AI 判定为 Host 查询，但未提供目标 IP。")
                return

            # 2. [统计聚合] AI 决定查看数据分布
            elif action == "stat_query":
                if not queries:
                    logger.error("AI 未生成有效的统计查询语句。")
                    return
                query_str = queries[0]
                logger.ai(f"AI 智能体路由决策: [全球统计聚合] -> 语法: {query_str}")
                logger.ai(f"统计维度 (Fields): {fields}")
                await handler.handle_stat_query(
                    query=query_str,
                    fields=fields,
                    user_intent=ai_query_str,
                    outdir=kwargs.get('outdir')
                )
                return

            # 3. [Icon 逆向] AI 决定反查图标
            elif action == "icon_query":
                logger.ai(f"AI 智能体路由决策: [Icon Hash 逆向] -> {target}")
                h = await IconHashCalculator.get_hash(target)
                if h:
                    candidate_queries = [h]
                else:
                    return

            # 4. [批量文件] AI 决定读取本地文件
            elif action == "bat_query":
                logger.ai(f"AI 智能体路由决策: [批量文件处理] -> {target}")
                path = Path(target)
                if path.exists():
                    with open(path, "r", encoding="utf-8") as f:
                        candidate_queries = [l.strip() for l in f if l.strip()]
                else:
                    logger.error(f"AI 提供的文件路径不存在: {target}")
                    return

            # 5. [通用搜索] 默认动作
            else:
                candidate_queries = queries

            # 同步 AI 的附加决策参数
            if plan.get('run_nuclei'): kwargs['nuclei'] = True
            final_scan_args = plan.get('nuclei_args', "")
            if fields and action == "fofa_search":
                kwargs['query_fields'] = fields

    # --- 非 AI 模式 ---
    elif kwargs.get('host_query'):
        # [修复] 手动模式同样清洗 target
        target = kwargs['host_query'].strip().strip("'").strip('"')
        await handler.handle_host_query(target, outdir=kwargs.get('outdir'))
        return
    elif kwargs.get('count_query'):
        # [修复] 对接统计查询逻辑
        await handler.handle_stat_query(
            kwargs['count_query'],
            kwargs.get('query_fields'),
            outdir=kwargs.get('outdir')
        )
        return
    elif kwargs.get('query'):
        candidate_queries = [kwargs['query']]
    elif kwargs.get('icon_query'):
        h = await IconHashCalculator.get_hash(kwargs['icon_query'])
        if h: candidate_queries.append(h)
    elif kwargs.get('bat_query'):
        path = Path(kwargs['bat_query'])
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                candidate_queries = [line.strip() for line in f if line.strip()]

    # [执行通用搜索任务]
    if candidate_queries:
        await handler.run_search_task(
            candidate_queries=candidate_queries,
            scan_format=kwargs.get('scan_format', False),
            outfile=kwargs.get('outfile'),
            outdir=kwargs.get('outdir'),
            export_format=kwargs.get('export_format'),
            pages=kwargs.get('pages', 0),
            key_word=kwargs.get('key_word'),
            include=kwargs.get('include'),
            query_fields=kwargs.get('query_fields'),
            ai_query=ai_query_str,
            nuclei=kwargs.get('nuclei', False),
            scan_args=final_scan_args,
            batch=kwargs.get('batch', False)
        )
    elif not ai_query_str:
        logger.warning("未检测到有效的查询任务。请使用 -h 查看帮助或使用 -ai 模式。")


if __name__ == "__main__":
    main()
