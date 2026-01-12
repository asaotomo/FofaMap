import time
import re
import datetime
import asyncio
from pathlib import Path
from colorama import Fore, Style
from prettytable import PrettyTable
import questionary

from config import settings
from utils.logger import logger
from utils.printer import ResultPrinter, print_header, print_item
from utils.helpers import FastChecker
from core.client import FofaClient
from core.excel import ExcelExporter
from core.scanner import NucleiScanner
from core.ai import DeepSeekHandler


class FofaHandler:
    def __init__(self):
        self.client = FofaClient()
        self.exporter = ExcelExporter()
        self.scanner = NucleiScanner()
        self.ai_handler = DeepSeekHandler()

        self.timestamp_suffix = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.project_dir = None

    async def init_user(self):
        """初始化并验证用户信息"""
        user_info = await self.client.check_login()
        # 将 user_info 挂载到 client 实例上，以便后续反思机制调用
        if user_info:
            self.client.user_info = user_info
        return user_info

    async def handle_host_query(self, host_query, user_intent=None):
        """[优化] 处理 Host 单体画像查询，集成 AI 风险评估"""
        d = await self.client.host_search(host_query)

        # [新增] 错误检查逻辑
        if not d:
            logger.error(f"未查询到 Host: {host_query} 的详细信息 (返回为空)")
            return
        if d.get("error"):
            logger.error(f"Host 查询失败: {d.get('errmsg', '未知错误')} (Target: {host_query})")
            return

        print_header(f"Host 深度画像: {d.get('host', 'N/A')}")
        print_item("IP地址", d.get('ip', 'N/A'))
        print_item("asn编号", d.get('asn', 'N/A'))
        print_item("asn组织", d.get('org', 'N/A'))
        print_item("国家名", d.get('country_name', 'N/A'))
        print_item("国家代码", d.get('country_code', 'N/A'))
        print_item("更新时间", d.get('update_time', 'N/A'))
        print(f"\n{Fore.CYAN}[*] 开放端口与服务详情:{Style.RESET_ALL}")

        table = PrettyTable(["Id", "Port", "Protocol", "Product", "Update_Time"])
        table.align = "c"
        table.align["Product"] = "l"
        table.padding_width = 1
        table.header_style = "title"
        table.border = False

        ports_data = d.get('ports', [])
        ports_data.sort(key=lambda x: x.get('port', 0))

        for idx, p in enumerate(ports_data, start=1):
            raw_products = p.get('products')
            prod_str = ""
            if raw_products:
                prod_list = [prod.get('product', '') for prod in raw_products]
                prod_str = ", ".join(prod_list[:3])
                if len(prod_list) > 3: prod_str += "..."

            port_val = p.get('port')
            # 高危端口标红
            port_display = f"{Fore.RED}{port_val}{Style.RESET_ALL}" if port_val in [22, 3389, 445, 1433, 6379,
                                                                                    7001] else port_val

            table.add_row(
                [idx, port_display, p.get('protocol', '').upper(), prod_str, p.get('update_time', '').split(' ')[0]])

        print(Fore.GREEN + str(table) + Style.RESET_ALL)

        # === AI 智能分析模块 ===
        if self.ai_handler.client:
            report_dir = Path("results") / f"host_analysis_{self.timestamp_suffix}"
            report_dir.mkdir(parents=True, exist_ok=True)
            report_path = report_dir / f"host_risk_report_{host_query}.md"

            report_content = await self.ai_handler.analyze_host_risk(d, user_intent=user_intent)

            if report_content:
                with open(report_path, "w", encoding="utf-8") as f:
                    f.write(report_content)
                logger.info(f"Host 风险评估报告已保存: {report_path}")

    async def handle_stat_query(self, query, fields, user_intent=None):
        """[优化] 处理统计聚合查询，集成 AI 态势分析"""
        stats_fields = fields if fields else "title,port,country"

        logger.info(f"正在聚合统计数据... Query: [{query}] Fields: [{stats_fields}]")
        data = await self.client.stats_search(query, stats_fields)
        if not data:
            logger.warning("未获取到统计数据。")
            return

        print_header("FOFA 全球资产统计聚合")
        print_item("查询内容", query)
        print_item("统计总数", f"{data.get('size', 0):,}")

        distinct = data.get("distinct", {})
        if distinct:
            print(f"\n{Fore.YELLOW}>> 唯一性计数 (Distinct):{Style.RESET_ALL}")
            for k, v in distinct.items():
                print(f"   - {k}: {Fore.CYAN}{v}{Style.RESET_ALL}")

        aggs = data.get("aggs", {})
        for key, val in aggs.items():
            if val:
                print(f"\n{Fore.GREEN}[*] 统计详情（{key.upper()}）:{Style.RESET_ALL}")
                has_regions = len(val) > 0 and 'regions' in val[0]
                headers = ["Id", "Name", "Count", "Regions"] if has_regions else ["Id", "Name", "Count"]
                table = PrettyTable(headers)
                table.align = "l"
                table.align["Count"] = "r"
                table.padding_width = 1
                table.header_style = "title"
                table.border = False

                for idx, item in enumerate(val, start=1):
                    name = item.get('name')
                    if len(str(name)) > 50: name = str(name)[:47] + "..."
                    count = f"{item.get('count'):,}"
                    row = [idx, name, count]
                    if has_regions:
                        regions = item.get('regions', [])
                        r_str = ", ".join([f"{r['name']}({r['count']})" for r in regions[:3]])
                        row.append(r_str)
                    table.add_row(row)
                print(Fore.GREEN + str(table) + Style.RESET_ALL)

        print_item("数据更新时间", data.get('lastupdatetime', 'N/A'))

        # === AI 智能分析模块 ===
        if self.ai_handler.client:
            report_dir = Path("results") / f"stat_analysis_{self.timestamp_suffix}"
            report_dir.mkdir(parents=True, exist_ok=True)
            report_path = report_dir / f"trend_report_{self.timestamp_suffix}.md"

            report_content = await self.ai_handler.analyze_stat_trends(data, query, user_intent=user_intent)

            if report_content:
                with open(report_path, "w", encoding="utf-8") as f:
                    f.write(report_content)
                logger.info(f"全球态势分析报告已保存: {report_path}")

    async def run_search_task(self, candidate_queries, scan_format, outfile, pages, key_word, include, query_fields,
                              ai_query, nuclei, scan_args, batch=False):
        """核心查询任务流程 (完整版，含 AI 自我修正逻辑)"""
        if not candidate_queries:
            logger.error("无有效查询语句")
            return

        if outfile:
            base_name = Path(outfile).stem
        else:
            raw = candidate_queries[0] if candidate_queries else "fofa_task"
            base_name = re.sub(r'[^\w\-]', '_', raw).strip('_')[:40]

        project_name = f"{base_name}_{self.timestamp_suffix}"
        self.project_dir = Path("results") / project_name
        self.project_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"项目目录: {self.project_dir}")

        all_results_aggregated = []
        merged_data_storage = {}
        merge_filename = f"batch_merge_{self.timestamp_suffix}.xlsx"
        global_excel_name = f"fofa_asset_all_{self.timestamp_suffix}.xlsx"

        final_fields_str = query_fields if query_fields else settings.search.fields
        temp_fields_list = final_fields_str.split(",")

        # [保留] 字段索引获取 (带异常处理)
        try:
            idx_host = temp_fields_list.index("host") if "host" in temp_fields_list else -1
            idx_proto = temp_fields_list.index("protocol") if "protocol" in temp_fields_list else -1
        except:
            idx_host = 0
            idx_proto = -1

        should_scan = nuclei

        logger.info(f"待执行查询: {len(candidate_queries)} 条")

        # === [新增] AI 修正相关的状态变量 ===
        consecutive_failures = 0
        has_retried = False

        # 使用 while 循环代替 for 循环，以便动态追加 AI 修正后的查询
        idx = 0
        try:
            while idx < len(candidate_queries):
                q_str = candidate_queries[idx]
                logger.info(f"执行 ({idx + 1}/{len(candidate_queries)}): [{q_str}]")

                current_batch_data = []
                found = 0
                current_fields = "host,protocol,ip,port" if scan_format else final_fields_str

                for page in range(1, pages + 1):
                    # [修改] 接收两个返回值：数据 和 实际使用的字段
                    data, effective_fields = await self.client.search(q_str, page, current_fields)

                    # [新增] 如果发生了降级，这里同步更新 current_fields，解决错位问题
                    if current_fields != effective_fields:
                        current_fields = effective_fields

                    if data:
                        # [保留] 兼容性修复 (处理一维数组)
                        if len(data) > 0 and isinstance(data[0], str):
                            data = [[x] for x in data]
                        found += len(data)
                        current_batch_data.extend(data)
                        logger.info(f"  -> P{page}: {len(data)} 条")
                        time.sleep(0.5)
                    else:
                        break

                # === [核心逻辑] 失败检测与 AI 反思 ===
                if found == 0:
                    logger.warning(f"  -> 无数据")
                    consecutive_failures += 1
                    remaining_queries = len(candidate_queries) - (idx + 1)
                    should_retry = (consecutive_failures >= 3) or (consecutive_failures > 0 and remaining_queries == 0)
                    if should_retry and ai_query and not has_retried:
                        # 获取前几次失败的样本
                        start_fail_idx = max(0, idx - 2)
                        failed_samples = candidate_queries[start_fail_idx: idx + 1]

                        # 获取用户信息用于鉴权 (尝试从 client 获取，如果不存在则给默认值)
                        user_info = getattr(self.client, "user_info", {"vip_level": 2})

                        # 调用 AI 进行反思
                        new_queries = await self.ai_handler.reflect_and_retry(ai_query, failed_samples, user_info)

                        if new_queries:
                            # 将新策略追加到队列末尾
                            candidate_queries.extend(new_queries)
                            has_retried = True  # 标记已触发修正
                            consecutive_failures = 0  # 重置计数器
                else:
                    # 只要有一次成功，计数器归零
                    consecutive_failures = 0

                if not current_batch_data:
                    idx += 1
                    continue

                if key_word:
                    keys = key_word.split(",")
                    current_batch_data = [i for i in current_batch_data if
                                          any(k.lower() in str(i).lower() for k in keys)]

                if not current_batch_data:
                    idx += 1
                    continue

                final_batch_data = current_batch_data
                current_fields_display = current_fields

                if not scan_format and (settings.fast_check.check_alive or include):
                    logger.info(
                        f"正在对 {len(current_batch_data)} 个目标进行存活检测 (Timeout={settings.fast_check.timeout}s)...")
                    urls = []
                    for item in current_batch_data:
                        c = ""
                        # [保留] 完整的 URL 构建逻辑
                        if idx_host != -1 and idx_host < len(item):
                            host_val = str(item[idx_host])
                            if host_val.startswith("http"):
                                c = host_val
                            else:
                                proto_val = "http"
                                if idx_proto != -1 and idx_proto < len(item):
                                    p = str(item[idx_proto]).lower()
                                    if "https" in p or "ssl" in p: proto_val = "https"
                                c = f"{proto_val}://{host_val}"
                        # [保留] 兜底逻辑
                        if not c:
                            for f in item:
                                s = str(f)
                                if s.startswith("http"): c = s; break
                        urls.append(c)

                    alive = await FastChecker.check_alive([u for u in urls if u], settings.fast_check.timeout)

                    new_res = []
                    for i, item in enumerate(current_batch_data):
                        u = urls[i]
                        code = alive.get(u, "Failed") if u else "N/A"
                        if include and str(code) not in include.split(","): continue
                        new_item = list(item)
                        new_item.append(code)
                        new_res.append(new_item)

                    final_batch_data = new_res
                    if "HTTP Status" not in current_fields_display:
                        current_fields_display += ",HTTP Status"

                if not final_batch_data:
                    idx += 1
                    continue

                print_header(f"查询结果: {q_str} (共 {len(final_batch_data)} 条)")
                ResultPrinter.print_fofa_data(final_batch_data, current_fields_display, is_ai_mode=bool(ai_query))

                safe_q = re.sub(r'[^\w]', '_', q_str).strip('_')[:30]
                all_results_aggregated.extend(final_batch_data)

                if not scan_format:
                    # [保留] Excel 保存逻辑
                    if settings.system.sheet_merge:
                        sheet_name = f"{idx + 1}_{safe_q}"
                        merged_data_storage[sheet_name] = final_batch_data
                        self.exporter.save(merged_data_storage, filename=str(self.project_dir / merge_filename),
                                           fields=current_fields_display.split(","))
                    else:
                        batch_filename = f"query_{idx + 1}_{safe_q}.xlsx"
                        self.exporter.save(final_batch_data, filename=str(self.project_dir / batch_filename),
                                           fields=current_fields_display.split(","))
                        self.exporter.save(all_results_aggregated, filename=str(self.project_dir / global_excel_name),
                                           fields=current_fields_display.split(","))

                # 循环索引递增
                idx += 1

        except KeyboardInterrupt:
            print(Fore.RED + "\n" + "=" * 50)
            logger.warning("[!] ⚠️  检测到用户强制中断 (Ctrl+C)")
            logger.warning(f"[!] 正在停止查询任务，已获取 {len(all_results_aggregated)} 条资产。正在生成报告...")
            print(Fore.RED + "=" * 50 + Style.RESET_ALL)
            pass

        if not all_results_aggregated:
            logger.warning("任务结束，无有效数据。")
            return

        logger.info(f"资产获取阶段结束。总计资产: {len(all_results_aggregated)} 条")

        targets = self.scanner._prepare_targets(all_results_aggregated)
        targets = sorted(list(set(targets)))
        targets_file_path = self.project_dir / f"targets_{self.timestamp_suffix}.txt"
        with open(targets_file_path, "w") as f:
            f.write("\n".join(targets))
        report_path = self.project_dir / f"report_{self.timestamp_suffix}.md"

        if ai_query:
            summary_text, ai_nuclei_args = await self.ai_handler.generate_summary(all_results_aggregated, ai_query)
            if summary_text:
                print(Fore.MAGENTA + "\n" + "=" * 20 + " AI 资产画像总结 " + "=" * 20 + Style.RESET_ALL)
                self.ai_handler._render_markdown_to_console(summary_text)

            if ai_nuclei_args and len(ai_nuclei_args) > 3:
                scan_args = ai_nuclei_args

            print(Fore.MAGENTA + "=" * 60 + Style.RESET_ALL)
            if targets:
                # 自动带时间戳和 [+] 前缀，无需手动 print(Fore.CYAN...)
                logger.info(f"待扫描目标预览 (Total: {len(targets)}):")

                # 列表内容保持 print 以维持缩进格式，避免每行都带时间戳
                preview_count = 15
                for t in targets[:preview_count]:
                    print(f"   - {t}")

                if len(targets) > preview_count:
                    print(f"   ... (剩余 {len(targets)-preview_count} 条，完整列表见: {targets_file_path.resolve()})")
                print(Fore.CYAN + "=" * 60 + Style.RESET_ALL)
            decision_color = Fore.GREEN if should_scan else Fore.RED
            decision_text = "YES (建议扫描)" if should_scan else "NO (不建议扫描)"
            logger.ai(f"初始决策 [run_nuclei]: {decision_color}{decision_text}{Style.RESET_ALL}")
            logger.ai(f"推荐 Nuclei 命令: nuclei {scan_args}")

            if not batch:
                # [关键修复] 使用 await .ask_async() 解决 asyncio 冲突
                action = await questionary.select(
                    "请选择下一步操作:",
                    choices=[
                        "🚀 执行 AI 推荐的扫描 (Execute Nuclei)",
                        "✏️  手动修改参数并扫描 (Edit Args)",
                        "🚫 仅生成报告，不扫描 (Skip Scan)",
                    ],
                    default="🚀 执行 AI 推荐的扫描 (Execute Nuclei)" if should_scan else "🚫 仅生成报告，不扫描 (Skip Scan)"
                ).ask_async()

                if "Execute Nuclei" in action:
                    should_scan = True
                elif "Edit Args" in action:
                    should_scan = True
                    # [关键修复] 使用 await .ask_async()
                    scan_args = await questionary.text("请输入 Nuclei 参数:", default=scan_args).ask_async()
                else:
                    should_scan = False

        if should_scan:
            scan_file_path = await self.scanner.run_scan(all_results_aggregated, project_dir=self.project_dir,
                                                         custom_args=scan_args, filename_suffix=self.timestamp_suffix)
            if ai_query and scan_file_path:
                await self.ai_handler.generate_vuln_report(all_results_aggregated, scan_file_path, str(report_path))
        elif ai_query:
            print(Fore.YELLOW + f"[-] 依据用户选择跳过漏洞扫描，直接生成资产报告。" + Style.RESET_ALL)
            await self.ai_handler.generate_asset_report(all_results_aggregated, ai_query, str(report_path))
