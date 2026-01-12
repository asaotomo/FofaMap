import json
import re
import asyncio
import datetime
from openai import AsyncOpenAI
from colorama import Fore, Style
from config import settings
from utils.logger import logger
import os


class DeepSeekHandler:
    def __init__(self):
        """
        畅想 1：支持多模型初始化。
        通过 settings 获取配置，实现对官方 API 和本地 (Ollama/LM Studio) 的兼容。
        """
        self.api_key = settings.userinfo.deepseek_api_key
        self.base_url = getattr(settings.userinfo, "base_url", "https://api.deepseek.com/v1")
        self.model_name = getattr(settings.userinfo, "model", "deepseek-chat")

        if not self.api_key:
            self.client = None
            logger.warning(f"未检测到 API Key，AI 模式将无法使用。当前 BaseURL: {self.base_url}")
        else:
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )

    def _render_markdown_to_console(self, md_text: str):
        """ [视觉优化] 保持您原有的彩色 Markdown 渲染逻辑 """
        if not md_text: return
        text = re.sub(r'^(#+)\s+(.*?)$', f"{Fore.CYAN}{Style.BRIGHT}\\2{Style.RESET_ALL}", md_text, flags=re.MULTILINE)
        text = re.sub(r'\*\*(.*?)\*\*', f"{Fore.YELLOW}\\1{Style.RESET_ALL}", text)
        text = re.sub(r'```(.*?)```', f"{Fore.GREEN}\\1{Style.RESET_ALL}", text, flags=re.DOTALL)
        text = re.sub(r'`(.*?)`', f"{Fore.GREEN}\\1{Style.RESET_ALL}", text)
        text = re.sub(r'^\s*-\s+', "  • ", text, flags=re.MULTILINE)
        print(text)

    async def strategic_planning(self, user_intent: str, user_info: dict) -> dict:
        """
        [AI 决策阶段] 智能路由 + 您的专家级指令集 (已集成 Host 详情与统计聚合)
        """
        if not self.client:
            logger.error("未配置 API Key")
            return None

        vip_level = user_info.get('vip_level', 0)
        level_name = {0: "注册用户", 1: "普通会员", 2: "高级会员(专业版)", 5: "企业版V2", 11: "个人版", 12: "专业版",
                      13: "商业版"}.get(vip_level,
                                        f"Level {vip_level}")

        logger.ai(f"当前用户等级: [{level_name}]")
        logger.ai(f"正在通过 [{self.model_name}] 结合 [专家指令集] 制定战法...")

        # === 核心：完整保留您的专家级指令集 ===
        system_prompt = f"""
        你是一个精通 FOFA 搜索引擎的安全专家。请根据用户需求，精准选择 API 接口并生成参数。

        ### 🕹️ 智能路由 (Action Routing) - 必须从以下 5 个动作中选择:
        1. **fofa_search**: [资产清单] 用户想获取具体的 IP/URL 列表时使用。 (默认动作)
           - *场景*: "帮我找 10 个通达OA", "查询 log4j 漏洞资产"。
        2. **host_query**: [单体画像] 用户提供了**具体的单个 IP**，想看它的详细标签、端口、产品。
           - *场景*: "分析 8.8.8.8", "查看这个 IP 开了哪些端口", "1.1.1.1 的详情"。
           - *注意*: 目标通常是 IP。
        3. **stat_query**: [统计聚合] 用户想看数据的**分布、排名、趋势** (Top 5)。
           - *场景*: "统计全球 Redis 的端口分布", "查看 Cobalt Strike 的国家排名", "分析最常见的 http title"。
           - *注意*: 这是一个宏观视角，不返回具体 IP。
        4. **icon_query**: [图标逆向] 用户提供 URL，想搜同类图标资产。
        5. **bat_query**: [批量文件] 用户提到了本地文件路径。

        ### 🔓 核心原则 (Crucial Distinction):
        1. **Search Query**: 全员可用 `body=`, `icon_hash=` 等高级语法。
        2. **Fields**: 严格受等级限制，越权会报错。
        3. **组合拳**: 使用 `||` 和 `&&` 聚合特征 (如 `app="Redis" && country="CN"`).

        ### 📊 统计聚合专用规则 (Stat Rules):
        仅当 action="stat_query" 时有效。支持的字段如下 (仅限这些):
        - `protocol`, `domain`, `port`, `title`, `os`, `server`, `country`, `asn`, `org`, `asset_type`, `fid`, `icp`
        - *示例1*: 用户查 "端口分布" -> fields="port"; 用户查 "国家排名" -> fields="country"。
        - *示列2*: 用户查 "redis在美国的分布情况" —> app="redis" && country="US" fields="country,port,org,asn"。

        ### 📚 搜索/列表全量字段权限表 (Fields Permission Guide):
        (仅用于 fofa_search，stat_query 请忽略此表)
        请根据用户等级 **{vip_level} ({level_name})** 智能选择 `fields`（其中企业会员全部可用）：
        **【Level 0+ 全员可用】(注册用户及以上)**
        - **网络层**: `ip`, `port`, `protocol`, `base_protocol`
        - **域名/主机**: `host`, `domain`, `link`
        - **基础指纹**: `title`, `server`, `os`, `header`, `banner`, `icp`, `jarm`
        - **地理位置**: `country`, `country_name`, `region`, `city`, `longitude`, `latitude`, `asn`, `org`
        - **证书基础**: `cert`, `cert.domain`, `cert.sn`
        - **证书详情**: `cert.issuer.org`, `cert.issuer.cn`, `cert.subject.org`, `cert.subject.cn`
        - **TLS信息**: `tls.ja3s`, `tls.version`, `cert.not_before`, `cert.not_after`

        **【Level 11+ 个人版及以上 和 Level 2 高级会员(专业版)及以上】(普通会员及以上)**
        - **Hash/Fid**: `header_hash`, `banner_hash`, `banner_fid`

        **【level 12+ 专业版及以上 和 Level 2 高级会员(专业版)及以上】(专业版及以上)**
        - **关键增强**: `product` (产品名), `product_category` (分类), `cname`, `lastupdatetime`

        **【Level 13+ 商业版本及以上】(商业版及以上)**
        - **高危字段**: `body` (网页正文), `icon_hash`,`fid` (指纹特征)
        - **深度验证**: `product.version`, `cert.is_valid`, `cname_domain`, `cert.is_match`, `cert.is_equal`
        
        **【Level 5 企业版V2】(企业版)**
        - **包含上述所有权限**，且额外独享:  `icon`, `structinfo`(结构化信息)
        
        ### 🧠 决策逻辑:
        1. **Action**: 判定动作。
        2. **Target**: host_query/icon/bat 模式的目标内容。
        3. **Queries**: 生成 FOFA 查询语句。
        4. **Fields**: 根据等级选择字段。
        5. **Analyze**: 视具体情况生成1-5条高质量的组合查询语句。大胆使用 `body=`, `app=`, `icon_hash=` 等语法进行搜索。

        ### 📝 返回格式 (JSON Only):
        {{
            "action": "fofa_search | host_query | stat_query | icon_query | bat_query",
            "target": "具体目标(IP/File/URL) 或 null",
            "queries": ["查询语句"],
            "fields": "逗号分隔的字段列表", 
            "run_nuclei": true/false
        }}
        """

        try:
            payload = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_intent}
                ],
                "temperature": 0.2
            }
            if "deepseek.com" in self.base_url or "openai.com" in self.base_url:
                payload["response_format"] = {"type": "json_object"}

            response = await self.client.chat.completions.create(**payload)
            content = response.choices[0].message.content
            content = re.sub(r'```json\s*|\s*```', '', content).strip()
            plan = json.loads(content)
            return plan
        except Exception as e:
            logger.error(f"AI 决策制定失败: {e}")
            return None

    async def reflect_and_retry(self, user_intent: str, failed_queries: list, user_info: dict) -> list:
        """
        [新增] 策略修正模式：当连续查询失败时，AI 分析原因并生成更宽泛的兜底查询
        """
        if not self.client: return []

        logger.ai(f"检测到连续失败，AI 正在进行策略反思与修正...")

        # 获取用户权限等级，决定字段
        vip_level = user_info.get('vip_level', 0)

        system_prompt = f"""
        你是一个FOFA高级搜索专家。

        【现状】
        用户想要查询："{user_intent}"
        但是，你生成的以下查询语句全部返回了 0 条数据（失败）：
        {json.dumps(failed_queries, ensure_ascii=False)}

        【反思与修正】
        请分析失败原因（可能是域名后缀猜错了、地域限制 region 过于严格、或者语法太具体）。
        请生成 3 条 **新的、更宽泛的** 修正查询语句。

        【修正策略】
        1. 【保守修正】：去掉最可能导致错误的 1 个条件（如去掉 region 或 city），保留核心指纹。
        2. 【模糊匹配】：使用 body= 或 title= 替换 host=，扩大搜索范围。
        3. 【极度宽泛】：仅保留最核心关键词（如 "关键词" && country="CN"），作为最后的兜底。
        4. 【域名猜想】：如果之前猜是.edu.cn等后缀，请尝试 .cn 或 .com，或者直接查中文关键词。

        【权限限制】
        用户等级 Level {vip_level}。请确保字段不越权。

        请仅返回 JSON 格式：
        {{
            "correction_reason": "简短分析失败原因",
            "new_queries": ["query1", "query2", "query3"]
        }}
        """

        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": system_prompt}],
                response_format={"type": "json_object"},
                temperature=0.4
            )
            content = json.loads(response.choices[0].message.content)

            reason = content.get("correction_reason", "未知")
            new_qs = content.get("new_queries", [])
            logger.ai(f"[反思中···] {reason}" + Style.RESET_ALL)
            if new_qs:
                logger.ai(f"[修正中···] 已重新生成 {len(new_qs)} 条新策略，追加执行...")
            return new_qs
        except Exception as e:
            logger.error(f"AI 修正策略生成失败: {e}")
            return []

    async def generate_summary(self, results: list, user_intent: str) -> tuple:
        """ [无损保留] 资产总结阶段及您的 Nuclei 参数指南 """
        if not self.client or not results: return None, None

        # 构建资产快照
        preview_lines = []
        for item in results[:30]:
            try:
                preview_lines.append(f"Info: {str(item)[0:100]}...")
            except:
                pass
        logger.ai("正在根据【实际发现的资产】进行资产画像分析与战术制定...")
        system_prompt = f"""
        你是一个精通漏洞挖掘的安全专家。用户最初需求：'{user_intent}'。
        资产样本如下：{json.dumps(preview_lines, ensure_ascii=False)}

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

        【输出要求】
        必须返回纯 JSON 格式 (不要用 Markdown 代码块包裹):
        {{
            "summary": "Markdown格式的资产画像总结。请重点指出识别到的【关键技术栈】(如 SpringBoot, Nginx) 和 【潜在高危面】(如 开放了 7001 端口)。",
            "nuclei_args": "构建好的命令行参数字符串 (例如: -as -tags spring,shiro -severity critical,high -rate-limit 150)"
        }}
        """

        try:
            payload = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": system_prompt}],
                "temperature": 0.3
            }
            if "deepseek.com" in self.base_url or "openai.com" in self.base_url:
                payload["response_format"] = {"type": "json_object"}

            response = await self.client.chat.completions.create(**payload)
            content = json.loads(re.sub(r'```json\s*|\s*```', '', response.choices[0].message.content).strip())
            return content.get("summary", ""), content.get("nuclei_args", "")
        except Exception as e:
            return None, None

    # --- [新增/优化] 针对 Host 聚合的分析 (带数据附录) ---
    async def analyze_host_risk(self, host_data: dict, user_intent: str = ""):
        """ [优化] AI 单体资产风险画像分析 + 原始数据附录 """
        if not self.client: return

        logger.ai("正在对单体资产进行深度风险画像分析...")

        # 提取关键信息给 AI
        context = {
            "ip": host_data.get('ip'),
            "org": host_data.get('org'),
            "ports": [p.get('port') for p in host_data.get('ports', [])],
            "products": [p.get('products') for p in host_data.get('ports', []) if p.get('products')],
            "update_time": host_data.get('update_time')
        }

        system_prompt = f"""
        你是一名高级渗透测试工程师和红队专家。请根据以下 FOFA Host 聚合数据，生成一份【单体资产风险画像】。

        用户意图: {user_intent or '资产审计'}
        资产概要: {json.dumps(context, ensure_ascii=False)}

        请输出 Markdown 报告，包含以下部分：
        1. **🛡️ 暴露面分析**: 点评开放的端口（特别是高危端口如 3389, 445, 22, 数据库端口等）和协议。
        2. **⚠️ 风险研判**: 根据识别到的产品（Product）和组件，推测可能存在的漏洞（如 Weblogic, OA, Shiro 等）。如果只是普通服务，评估其被攻击的可能性。
        3. **🎯 攻击路径推演**: 如果你是攻击者，你会优先从哪里入手？
        4. **📝 综合评分**: 给出一个风险等级 (高/中/低) 和一句话总结。

        保持简洁、专业，直接给出干货。
        """

        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": system_prompt}],
                temperature=0.3
            )
            report = response.choices[0].message.content

            # --- [关键优化] 生成原始数据附录 ---
            appendix = "\n\n---\n### 📎 附录：原始资产数据快照 (Host Data)\n"
            appendix += f"**IP**: `{host_data.get('ip', 'N/A')}` | **ASN**: `{host_data.get('asn', 'N/A')} {host_data.get('org', '')}`\n\n"
            appendix += "| Port | Protocol | Product | Update Time |\n"
            appendix += "| :---: | :---: | :--- | :--- |\n"

            ports_data = host_data.get('ports', [])
            ports_data.sort(key=lambda x: x.get('port', 0))

            for p in ports_data:
                prod_list = [pr.get('product', '') for pr in p.get('products', [])]
                prod_str = ", ".join(prod_list[:3]) + ("..." if len(prod_list) > 3 else "")
                appendix += f"| {p.get('port')} | {p.get('protocol')} | {prod_str} | {p.get('update_time', '').split(' ')[0]} |\n"

            final_report = report + appendix

            print(Fore.MAGENTA + "\n" + "=" * 20 + " AI Host 风险画像 " + "=" * 20 + Style.RESET_ALL)
            self._render_markdown_to_console(report)  # 控制台只打印 AI 分析部分，避免刷屏
            return final_report  # 返回给文件写入的是带附录的完整版

        except Exception as e:
            logger.error(f"Host 分析失败: {e}")

    # --- [新增/优化] 针对统计聚合的分析 (带数据附录) ---
    async def analyze_stat_trends(self, stat_data: dict, query: str, user_intent: str = ""):
        """ [优化] AI 全球态势感知分析 + 统计数据附录 """
        if not self.client: return

        logger.ai(f"AI 正在结合查询 [{query}] 进行全球态势分析...")

        # 提取 Top 数据给 AI
        context_aggs = {}
        for k, v in stat_data.get('aggs', {}).items():
            context_aggs[k] = v[:5] if isinstance(v, list) else v

        system_prompt = f"""
        你是一名网络空间测绘数据分析师。请根据 FOFA 的统计聚合数据，生成一份【FOFAMAP-全球态势分析小结】。

        查询语句: {query}
        用户意图: {user_intent or '行业分析'}
        统计数据(Top5): {json.dumps(context_aggs, ensure_ascii=False)}

        请输出 Markdown 报告，包含以下部分：
        1. **📊 分布特征**: 分析数据在国家(country)、端口(port)或产品版本上的分布规律。是否有明显的地域集中性？
        2. **🔍 异常洞察**: 是否有非标准端口运行标准服务？或者某种异常的 Title 占据了榜首？
        3. **🌍 宏观影响**: 该组件或资产在全球范围内的普及度和潜在影响面。
        4. **💡 结论**: 一句话总结该查询反映的态势。

        不要列举枯燥的数据，重点在于【分析】和【洞察】。
        """

        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": system_prompt}],
                temperature=0.3
            )
            report = response.choices[0].message.content

            # --- [关键优化] 生成统计数据附录 ---
            appendix = "\n\n---\n### 📎 附录：统计数据快照 (Statistical Data)\n"
            appendix += f"**Query**: `{query}` | **Total Matches**: `{stat_data.get('size', 0)}`\n"

            # 1. 唯一性计数表
            distinct = stat_data.get("distinct", {})
            if distinct:
                appendix += "\n#### 1. 唯一性计数 (Distinct Count)\n"
                for k, v in distinct.items():
                    appendix += f"- **{k}**: {v}\n"

            # 2. 聚合详情表
            aggs = stat_data.get("aggs", {})
            for field_name, items in aggs.items():
                if not items: continue
                appendix += f"\n#### 2. Top {field_name.upper()} Ranking\n"
                appendix += "| Rank | Name | Count | Top Regions |\n"
                appendix += "| :---: | :--- | :---: | :--- |\n"

                for idx, item in enumerate(items, start=1):
                    name = str(item.get('name', '')).replace('|', '\|')  # 转义 Markdown 表格符
                    count = item.get('count', 0)
                    regions = item.get('regions', [])
                    r_str = ", ".join([f"{r['name']}({r['count']})" for r in regions[:3]])
                    appendix += f"| {idx} | {name} | {count} | {r_str} |\n"

            final_report = report + appendix

            print(Fore.MAGENTA + "\n" + "=" * 20 + "FOFAMAP-AI全球态势分析 " + "=" * 20 + Style.RESET_ALL)
            self._render_markdown_to_console(report)  # 控制台只打印分析部分
            return final_report  # 完整版写入文件

        except Exception as e:
            logger.error(f"Stat 分析失败: {e}")

    # 保留 generate_asset_report 和 generate_vuln_report
    async def generate_asset_report(self, results: list, user_intent: str, filename: str):
        if not self.client: return
        logger.ai("正在生成《FOFAMAP-资产暴露面普查报告》...")
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        context = f"资产总数: {len(results)}\n需求: {user_intent}"
        system_prompt = f"撰写专业的报告。标题：《FOFAMAP-互联网资产暴露面普查报告》，日期：{current_date}。"
        await self._call_ai_and_save(system_prompt, context, filename)

    async def generate_vuln_report(self, results: list, scan_file_path: str, filename: str):
        """
        [AI 报告阶段] 综合安全评估报告生成 (资产暴露面 + 漏洞扫描结果)
        """
        if not self.client: return
        logger.ai("正在生成《FOFAMAP-综合安全评估报告》...")

        # 1. 获取当前时间
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")

        # 2. 准备资产数据 (取前30条作为样本，避免 Token 溢出)
        asset_context = ""
        try:
            sample_assets = []
            for item in results[:30]:
                # 简单拼接每行数据的前5列 (通常是 URL, IP, Port, Title 等)
                row_str = " | ".join([str(x) for x in item[:5]])
                sample_assets.append(row_str)
            asset_context = "\n".join(sample_assets)
        except Exception as e:
            asset_context = f"资产数据提取失败: {e}"

        # 3. 准备漏洞数据 (读取 Nuclei 扫描结果)
        vuln_context = ""
        try:
            # 确保路径是字符串
            log_path = str(scan_file_path)
            if not os.path.exists(log_path):
                vuln_context = "未找到扫描日志文件。"
            else:
                with open(log_path, "r", encoding="utf-8", errors='ignore') as f:
                    logs = f.read()

                # 提取关键漏洞日志 (Critical/High/Medium/Low)
                important_logs = [
                    line for line in logs.split('\n')
                    if any(x in line.lower() for x in ['[critical]', '[high]', '[medium]', '[low]'])
                ]

                if not important_logs:
                    vuln_context = "本次扫描未发现 Critical/High/Medium/Low 级别的漏洞。"
                else:
                    # 限制长度防止 Token 爆炸
                    vuln_context = "\n".join(important_logs[:150])
                    if len(important_logs) > 150:
                        vuln_context += "\n...(剩余漏洞日志已省略)..."
        except Exception as e:
            vuln_context = f"漏洞日志读取失败: {e}"

        # 4. 构建专家级 Prompt
        system_prompt = f"""
        请根据提供的【资产测绘数据】和【漏洞扫描日志】，撰写一份完整的 Markdown 格式《FOFAMAP-综合安全评估报告》。

        ### 报告结构要求:
        1. **标题**: 必须是《FOFAMAP-综合安全评估报告》，第二行必须是：报告日期：{current_date}。
        2. **资产概览**: 基于测绘数据，统计目标数量，分析开放端口分布、主要运行的服务/中间件架构。
        3. **漏洞概览**: 基于扫描日志，统计漏洞数量、等级分布。
        4. **详细风险分析**: 
           - 如果发现漏洞：请详细列出漏洞名称、危害等级及对应的资产。
           - 如果**未发现漏洞**：请重点分析**资产暴露面风险**（例如：虽无漏洞，但开放了 3389/22 端口存在暴力破解风险，或使用了老旧的 HTTP 服务）。
        5. **修复与加固建议**: 针对发现的问题或潜在风险提供具体的安全加固建议。

        请注意：报告语言要专业、客观，如果是空日志不要捏造漏洞。
        """

        user_content = f"""
        【部分一：资产测绘数据样本 (FOFA)】
        {asset_context}

        【部分二：漏洞扫描日志 (Nuclei)】
        {vuln_context}
        """

        await self._call_ai_and_save(system_prompt, user_content, filename)

    async def _call_ai_and_save(self, system_prompt, user_content, filename):
        try:
            # 使用 self.model_name 以支持配置切换 (DeepSeek/Ollama)
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.3
            )
            report_text = response.choices[0].message.content

            if not isinstance(report_text, str):
                report_text = str(report_text)

            with open(filename, "w", encoding="utf-8") as f:
                f.write(report_text)

            print(Fore.MAGENTA + "\n" + "=" * 20 + " AI 报告预览 " + "=" * 20 + Style.RESET_ALL)
            self._render_markdown_to_console(report_text[:800] + "\n\n(......完整报告内容过长，已省略......)")
            logger.info(f"完整报告已保存至: {filename}")

        except Exception as e:
            logger.error(f"报告生成出错: {e}")
