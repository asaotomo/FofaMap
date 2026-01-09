from rich.console import Console
from rich.table import Table
from rich import box
from colorama import Fore, Style
from config import settings

# 初始化 Rich 控制台
console = Console()


# --- UI 辅助函数 ---

def print_header(title):
    print(Fore.RED + f"======{title}=======" + Style.RESET_ALL)


def print_item(key, value):
    print(f"{Fore.GREEN}[+]{Style.RESET_ALL} {Fore.GREEN}{key}:{Style.RESET_ALL}{value}")


def print_config():
    print_header("基础配置")
    print(f"{Fore.GREEN}[*] 日志记录:{Style.RESET_ALL}{'开启' if settings.system.logger else '关闭'}")
    print(f"{Fore.GREEN}[*] 存活检测:{Style.RESET_ALL}{'开启' if settings.fast_check.check_alive else '关闭'}")
    print(f"{Fore.GREEN}[*] 合并导出:{Style.RESET_ALL}{'开启' if settings.system.sheet_merge else '关闭'}")
    print(f"{Fore.GREEN}[*] 每页查询数量:{Style.RESET_ALL}{settings.search.size}条/页")


def print_userinfo(user_info):
    print_header("个人信息")
    if not user_info: return
    email = user_info.get('email', '')
    masked_email = email[:2] + "****" + email[-1:] if len(email) > 4 else email
    print_item("邮箱", masked_email)
    print_item("用户名", user_info.get('username'))
    print_item("F币剩余数量", user_info.get('fcoin'))
    print_item("是否是VIP", str(user_info.get('isvip')))
    print_item("VIP等级", user_info.get('vip_level'))


class ResultPrinter:
    @staticmethod
    def print_fofa_data(data, fields_str, is_ai_mode=False):
        """
        [双模式智能版]
        Args:
            is_ai_mode (bool):
                - True (AI模式): 启用白名单过滤，屏蔽 AI 推荐的冗余字段，只看核心。
                - False (用户模式): 尊重用户配置，显示所有字段，但智能控制宽度。
        """
        if not data: return

        # === 1. 字段筛选逻辑 ===
        raw_headers = [f.strip() for f in fields_str.split(",")]

        display_indices = []  # 记录需要显示的列索引
        display_headers = []  # 记录需要显示的列名

        # 定义核心白名单 (仅在 AI 模式下生效)
        AI_WHITELIST = [
            "HOST", "IP", "PORT", "PROTOCOL",
            "TITLE", "SERVER", "HTTP STATUS",
            "COUNTRY_NAME", "CNAME", "URL", "DOMAIN"
        ]

        for idx, h in enumerate(raw_headers):
            h_upper = h.upper()

            # 【核心逻辑分支】
            if is_ai_mode:
                # AI 模式：只显示白名单内的字段 + 状态码
                if h_upper in AI_WHITELIST or h_upper == "HTTP STATUS":
                    display_indices.append(idx)
                    display_headers.append(h_upper)
            else:
                # 用户模式：显示所有字段 (照单全收)
                display_indices.append(idx)
                display_headers.append(h_upper)

        # 智能布局: 如果列数很少，不强行撑满屏幕
        should_expand = len(display_headers) >= 4

        # === 2. 创建表格 ===
        table = Table(
            show_header=True,
            header_style="bold magenta",
            box=box.SIMPLE,
            expand=should_expand,
            show_lines=False,
            collapse_padding=True,
            pad_edge=False
        )

        # ID 列
        table.add_column("ID", justify="center", style="cyan", no_wrap=True, width=4)

        current_col_count = 1

        for header in display_headers:
            current_col_count += 1

            # === 3. 样式分配 (Host优先策略) ===

            # [Host/URL]: 无论什么模式，都是最重要的，给最大权重
            if header in ["HOST", "URL", "LINK", "DOMAIN"]:
                table.add_column(header, no_wrap=True, overflow="ellipsis", ratio=3, min_width=25)

            # [Title]: 次要信息，限制宽度，防止挤压 Host
            elif header == "TITLE":
                table.add_column(header, no_wrap=True, overflow="ellipsis", ratio=1, max_width=25)

            # [长文本垃圾信息]: Cert/Product/Body
            # 在用户模式下虽然会显示，但必须截断，不能炸屏
            elif header in ["CERT", "PRODUCT", "BANNER", "HEADER", "BODY", "JARM"]:
                table.add_column(header, no_wrap=True, overflow="ellipsis", max_width=20)

            # [短字段]: IP/Port/Status
            else:
                # 前5列给予最小宽度保护
                if current_col_count <= 5 or header == "HTTP STATUS":
                    table.add_column(header, no_wrap=True, min_width=6)
                else:
                    table.add_column(header, no_wrap=True, overflow="ellipsis", max_width=15)

        # === 4. 填充数据 ===
        for idx, item in enumerate(data, start=1):
            row_data = []
            for col_idx in display_indices:
                if col_idx < len(item):
                    val = item[col_idx]
                    row_data.append(str(val) if val is not None else "")
                else:
                    row_data.append("")

            table.add_row(str(idx), *row_data)

        # === 5. 打印 ===
        console.print(table)

        # 提示信息
        if is_ai_mode:
            hidden = len(raw_headers) - len(display_headers)
            if hidden > 0:
                print(
                    Fore.LIGHTBLACK_EX + f"[*] AI 智能精简: 已隐藏 {hidden} 个冗余字段(如Cert)，完整数据请查看 Excel。" + Style.RESET_ALL)
        elif len(data) >= 100:
            print(Fore.LIGHTBLACK_EX + f"[*] 当前页显示 {len(data)} 条数据。" + Style.RESET_ALL)

    @staticmethod
    def print_nuclei_summary(result_file):
        """ 保持不变 """
        if not result_file.exists(): return
        try:
            with open(result_file, "r", encoding="utf-8", errors='ignore') as f:
                content = f.read()
        except:
            return
        # ... (省略重复代码，保持原样即可)
        critical = content.count("[critical]")
        high = content.count("[high]")
        medium = content.count("[medium]")
        low = content.count("[low]")
        info = content.count("[info]")

        print(Fore.RED + "\n======漏洞统计=======" + Style.RESET_ALL)
        print(Fore.GREEN + f"扫描结果文件: {result_file}")
        print(Fore.LIGHTRED_EX + f"[+] [critical]: {critical}")
        print(Fore.LIGHTYELLOW_EX + f"[+] [high]    : {high}")
        print(Fore.LIGHTCYAN_EX + f"[+] [medium]  : {medium}")
        print(Fore.LIGHTGREEN_EX + f"[+] [low]     : {low}")
        print(Fore.LIGHTBLUE_EX + f"[+] [info]    : {info}" + Style.RESET_ALL)