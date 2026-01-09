import sys
import time
from colorama import Fore, Style, init

# 初始化颜色自动重置
init(autoreset=True)


class Logger:
    def __init__(self):
        self.log_file = None
        # 延迟加载配置以避免循环导入，或者简单地默认开启/关闭
        # 这里我们尝试打开日志文件，如果不需要可以后续在 config 中控制
        try:
            self.log_file = open("fofamap.log", "a", encoding="utf-8")
        except Exception as e:
            print(f"[!] 无法创建日志文件: {e}")

    def _get_time(self):
        """获取 SQLMap 风格的时间戳 [HH:MM:SS]"""
        return time.strftime("%H:%M:%S")

    def _print(self, color, symbol, msg):
        """核心打印逻辑"""
        timestamp = self._get_time()

        # 控制台输出：带颜色
        # 格式: [12:00:00] [+] 消息
        print(f"{Fore.CYAN}[{timestamp}]{Style.RESET_ALL} {color}{symbol} {msg}{Style.RESET_ALL}")

        # 文件记录：去除颜色 (简单处理)
        if self.log_file:
            clean_msg = f"[{timestamp}] {symbol} {msg}\n"
            self.log_file.write(clean_msg)
            self.log_file.flush()

    def info(self, msg):
        self._print(Fore.GREEN, "[+]", msg)

    def error(self, msg):
        self._print(Fore.RED, "[!]", msg)

    def warning(self, msg):
        self._print(Fore.YELLOW, "[-]", msg)

    def ai(self, msg):
        # AI 专用颜色
        self._print(Fore.MAGENTA, "[AI]", msg)


# 全局单例
logger = Logger()