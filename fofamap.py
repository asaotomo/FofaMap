# -*- coding: utf-8 -*-
import argparse
import configparser
import fofa
import colorama
import xlsxwriter


# 当前软件版本信息
def banner():
    print(colorama.Fore.LIGHTGREEN_EX + """
 _____      __       __  __             
|  ___|__  / _| __ _|  \/  | __ _ _ __  
| |_ / _ \| |_ / _` | |\/| |/ _` | '_ \ 
|  _| (_) |  _| (_| | |  | | (_| | |_) |
|_|  \___/|_|  \__,_|_|  |_|\__,_| .__/ 
                                 |_|   V1.0.0  
#Coded by Asaotomo  Update:2021.12.29""")


def out_file(filename, database, scan_format):
    print(colorama.Fore.RED + "======文档输出=======")
    if scan_format:
        field = "ip,port".split(",")  # 获取查询参数
    else:
        field = config.get("fields", "fields").split(",")  # 获取查询参数
    column_lib = {1: 'A', 2: 'B', 3: 'C', 4: 'D', 5: 'E', 6: 'F', 7: 'G', 8: 'H', 9: 'I', 10: 'J', 11: 'K', 12: 'L',
                  13: 'M', 14: 'N', 15: 'O', 16: 'P', 17: 'Q', 18: 'R', 19: 'S', 20: 'T', 21: 'U', 22: 'V', 23: 'W',
                  24: 'X', 25: 'Y', 26: 'Z'}
    workbook = xlsxwriter.Workbook(filename)
    worksheet = workbook.add_worksheet()
    worksheet.set_column('A:{}'.format(column_lib[len(field)]), 30)
    title_format = workbook.add_format(
        {'font_size': 14, 'border': 1, 'bold': True, 'font_color': 'white', 'bg_color': '#4BACC6', 'align': 'center',
         'valign': 'center', 'text_wrap': True})
    content_format = workbook.add_format({'border': 1, 'align': 'left', 'valign': 'vcenter', 'text_wrap': True})
    i = 1
    row = 1
    col = 0
    for column in field:
        worksheet.write('{}1'.format(column_lib[i]), column, title_format)
        i += 1
    for item in database:
        for n in range(len(field)):
            worksheet.write(row, col + n, item[n], content_format)
        row = row + 1
    workbook.close()
    print(colorama.Fore.GREEN + "文档输出成功！文件名为：{}".format(filename))


def get_userinfo():
    # 获取用户信息
    user_info = client.get_userinfo()
    email = user_info["email"]  # 查询用户邮箱
    username = user_info["username"]  # 查询用户名
    fcoin = user_info["fcoin"]  # 查询F币剩余数量
    isvip = user_info["isvip"]  # 查询用户是否为VIP
    vip_level = user_info["vip_level"]  # 查询用户VIP等级
    print(colorama.Fore.RED + "======个人信息=======")
    print(colorama.Fore.GREEN + "邮箱：{}".format(email))
    print(colorama.Fore.GREEN + "用户名：{}".format(username))
    print(colorama.Fore.GREEN + "F币剩余数量：{}".format(fcoin))
    print(colorama.Fore.GREEN + "是否是VIP：{}".format(isvip))
    print(colorama.Fore.GREEN + "VIP等级：{}".format(vip_level))


def get_search(query_str, scan_format):
    start_page = config.getint("page", "start_page")
    end_page = config.getint("page", "end_page")
    if scan_format:
        fields = "ip,port"  # 获取查询参数
    else:
        fields = config.get("fields", "fields")  # 获取查询参数

    # query_str = config.get("query_str", "query_str")  # 获取查询FOFA语句
    print(colorama.Fore.RED + "======查询内容=======")
    print(colorama.Fore.GREEN + "查询语句：{}".format(query_str))
    print(colorama.Fore.GREEN + "查询参数：{}".format(fields))
    print(colorama.Fore.GREEN + "查询页数：{}-{}".format(start_page, end_page))
    print(colorama.Fore.RED + "======查询结果=======")
    database = []
    if fields == "ip,port":
        for page in range(start_page, end_page):  # 从第1页查到第50页
            data = client.get_data(query_str, page=page, fields=fields)  # 查询第page页数据的ip和城市
            for ip, port in data["results"]:
                if port == "80":
                    print(colorama.Fore.GREEN + "{}".format(ip))
                else:
                    print(colorama.Fore.GREEN + "{}:{}".format(ip, port))  # 打印出每条数据的对应内容
            database = database + data["results"]
    else:
        for page in range(start_page, end_page):  # 从第1页查到第50页
            field = fields.split(",")
            data = client.get_data(query_str, page=page, fields=fields)  # 查询第page页数据的ip和城市
            for item in data["results"]:
                i = 0
                s = ""
                for key in field:
                    s += key + ":" + item[i] + " "
                    i += 1
                print(colorama.Fore.GREEN + s)  # 打印出每条数据的对应内容
            database = database + data["results"]
    return database


if __name__ == '__main__':
    # 获取版本信息
    banner()
    parser = argparse.ArgumentParser(
        description="SearchMap (A fofa API information collection tool)")
    parser.add_argument('-q', '--query', help='Fofa Query Statement')
    parser.add_argument('-s', '--scan_format', help='Output Scan Format', action='store_true')
    parser.add_argument('-o', '--outfile', default="fofa.xlsx", help='File Save Name')
    args = parser.parse_args()
    query_str = args.query
    filename = args.outfile
    scan_format = args.scan_format
    if query_str:
        # 初始化参数
        config = configparser.ConfigParser()
        colorama.init(autoreset=True)
        # 读取配置文件
        config.read('fofa.ini', encoding="utf-8")
        # 生成一个fofa客户端实例
        client = fofa.Client()
        # 获取账号信息
        get_userinfo()
        # 获取查询信息
        database = get_search(query_str, scan_format)
        # 输出excel文档
        out_file(filename, database, scan_format)
