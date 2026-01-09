import asyncio
import shutil
import re
import sys
import platform
import os
from pathlib import Path
from colorama import Fore, Style
from utils.logger import logger
from utils.printer import ResultPrinter


class NucleiScanner:
    def __init__(self):
        self.nuclei_path = self._locate_binary()
        self.base_results_dir = Path("results")
        self.base_results_dir.mkdir(exist_ok=True)

    def _locate_binary(self):
        system_type = platform.system().lower()
        is_windows = "windows" in system_type
        binary_names = ["nuclei.exe"] if is_windows else ["nuclei", "nuclei.exe"]

        path_in_env = shutil.which("nuclei")
        if path_in_env:
            print(f"{Fore.GREEN}[+] 发现系统环境变量中的 Nuclei: {Style.RESET_ALL}{path_in_env}")
            return path_in_env

        search_paths = [Path.cwd(), Path(__file__).parent.parent]
        for path in search_paths:
            for bin_name in binary_names:
                target = path / bin_name
                if target.exists() and target.is_file():
                    if not is_windows and not os.access(target, os.X_OK):
                        try:
                            os.chmod(target, 0o755)
                            logger.info(f"已自动赋予执行权限: {target}")
                        except:
                            pass
                    logger.info(f"发现本地目录中的 Nuclei: {target}")
                    return str(target.absolute())
        return None

    async def run_scan(self, targets: list, project_dir: Path, custom_args: str = None, filename_suffix: str = ""):
        if not self.nuclei_path:
            logger.error("未找到 Nuclei！请先安装或将 nuclei 可执行文件放入项目根目录。")
            return None

        if not targets: return None

        target_list = self._prepare_targets(targets)
        if not target_list:
            logger.warning("没有有效的 HTTP 目标，跳过扫描")
            return None

        project_dir.mkdir(parents=True, exist_ok=True)

        suffix = f"_{filename_suffix}" if filename_suffix else ""
        target_file = project_dir / f"targets{suffix}.txt"
        result_file = project_dir / f"nuclei_result{suffix}.txt"

        with open(target_file, "w", encoding="utf-8") as f:
            f.write("\n".join(target_list))

        logger.info(f"已生成目标列表: {target_file} (共 {len(target_list)} 个)")
        logger.info("正在启动 Nuclei 引擎 (已开启实时进度)...")

        args_str = custom_args if custom_args else ""
        args_list = args_str.split()

        cmd = [self.nuclei_path, "-l", str(target_file), "-o", str(result_file), "-stats"] + args_list

        # [修改] 移除了强制添加 -nc 的逻辑

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            async def read_stream(stream, is_stderr=False):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    line_str = line.decode('utf-8', errors='replace').strip()
                    if line_str:
                        self._print_live_line(line_str)

            await asyncio.gather(
                read_stream(process.stdout),
                read_stream(process.stderr, is_stderr=True)
            )

            await process.wait()

            if process.returncode == 0:
                print("\n")
                logger.info(f"扫描完成！结果已保存: {result_file}")
                self._print_summary(result_file)
                return result_file
            else:
                print("\n")
                logger.warning("Nuclei 扫描结束 (可能被中断或有错误)")
                return result_file if result_file.exists() else None

        except Exception as e:
            logger.error(f"扫描执行失败: {e}")
            return None

    def _print_live_line(self, line: str):
        colored_line = line
        is_progress = "|" in line and "Templates:" in line and "RPS:" in line

        if "[critical]" in line:
            colored_line = line.replace("[critical]", f"{Fore.RED}[critical]{Style.RESET_ALL}")
        elif "[high]" in line:
            colored_line = line.replace("[high]", f"{Fore.LIGHTRED_EX}[high]{Style.RESET_ALL}")
        elif "[medium]" in line:
            colored_line = line.replace("[medium]", f"{Fore.YELLOW}[medium]{Style.RESET_ALL}")
        elif "[low]" in line:
            colored_line = line.replace("[low]", f"{Fore.CYAN}[low]{Style.RESET_ALL}")
        elif "[info]" in line:
            colored_line = line.replace("[info]", f"{Fore.BLUE}[info]{Style.RESET_ALL}")

        if is_progress:
            sys.stdout.write(f"\r{colored_line}   ")
            sys.stdout.flush()
        else:
            sys.stdout.write(f"\r{colored_line}\n")
            sys.stdout.flush()

    def _prepare_targets(self, raw_data):
        urls = []
        for item in raw_data:
            if isinstance(item, str):
                urls.append(item if item.startswith("http") else f"http://{item}")
                continue
            candidate = None
            protocol = "http"
            for f in item:
                if f in ["http", "https"]: protocol = f; break
            for f in item:
                s = str(f)
                if "." in s and " " not in s:
                    candidate = s if s.startswith("http") else f"{protocol}://{s}"
                    break
            if candidate: urls.append(candidate)
        return list(set(urls))

    def _print_summary(self, result_file):
        ResultPrinter.print_nuclei_summary(result_file)