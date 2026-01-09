import xlsxwriter
import time
import re
from pathlib import Path
from utils.logger import logger
from config import settings


class ExcelExporter:
    def __init__(self):
        # 默认目录，作为保底
        self.default_root = Path("results")
        self.default_root.mkdir(exist_ok=True)

    def save(self, data, filename: str = None, fields: list = None):
        """
        保存查询结果到 Excel (支持单 Sheet 和多 Sheet 合并)

        :param data:
            - 如果是 list: 单 Sheet 模式
            - 如果是 dict: 多 Sheet 模式, 格式 {"SheetName": [rows], ...}
        :param filename: 文件名
        :param fields: 表头字段列表
        """
        if not data:
            logger.warning("没有数据需要保存，跳过 Excel 导出")
            return None

        # 1. 路径处理
        if not filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"fofa_result_{timestamp}.xlsx"

        file_path_obj = Path(filename)
        if len(file_path_obj.parts) > 1:
            final_path = file_path_obj
        else:
            final_path = self.default_root / filename

        if not str(final_path).endswith(".xlsx"):
            final_path = final_path.with_suffix(".xlsx")

        final_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            workbook = xlsxwriter.Workbook(str(final_path))

            # 定义样式
            header_format = workbook.add_format({
                'bold': True, 'font_color': 'white', 'bg_color': '#4BACC6',
                'align': 'center', 'valign': 'vcenter', 'border': 1, 'font_size': 12
            })
            cell_format = workbook.add_format({
                'border': 1, 'align': 'left', 'valign': 'vcenter', 'text_wrap': False
            })
            id_format = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter'})

            # 解析表头
            if fields:
                field_list = fields.split(",") if isinstance(fields, str) else fields
            else:
                field_list = settings.search.fields.split(",")
            headers = ["ID"] + [f.upper() for f in field_list]

            # --- 内部函数：写入单个 Worksheet ---
            def write_worksheet(sheet_name, rows):
                # 清洗 Sheet 名称 (Excel 不允许 []:*?/\ 且最长31字符)
                clean_name = re.sub(r'[\[\]:*?/\\]', '_', str(sheet_name))
                clean_name = clean_name[:31]  # 截断

                worksheet = workbook.add_worksheet(clean_name)

                # 写入表头
                worksheet.set_row(0, 25)
                for col_num, header in enumerate(headers):
                    worksheet.write(0, col_num, header, header_format)
                    width = 30 if header in ["URL", "HOST", "TITLE"] else (
                        10 if header in ["ID", "PORT", "CTRY"] else 20)
                    worksheet.set_column(col_num, col_num, width)

                # 写入数据
                for row_num, item in enumerate(rows, start=1):
                    worksheet.write(row_num, 0, row_num, id_format)
                    for col_num, cell_data in enumerate(item, start=1):
                        worksheet.write(row_num, col_num, str(cell_data), cell_format)

            # --- 根据数据类型分发逻辑 ---
            if isinstance(data, dict):
                # 多 Sheet 模式 (合并导出)
                for s_name, s_data in data.items():
                    if s_data:  # 只写入有数据的 Sheet
                        write_worksheet(s_name, s_data)
                logger.info(f"多 Sheet 合并导出成功 ({len(data)} 个任务)")
            else:
                # 单 Sheet 模式 (常规导出)
                write_worksheet("FOFA资产", data)

            workbook.close()
            logger.info(f"Excel 已保存至: {final_path}")
            return final_path

        except Exception as e:
            logger.error(f"Excel 保存失败: {e}")
            return None