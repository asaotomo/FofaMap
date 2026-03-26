import csv
import xlsxwriter
import time
import re
from pathlib import Path
from utils.logger import logger
from config import settings


class ExcelExporter:
    SUPPORTED_FORMATS = {"xlsx", "csv"}

    def __init__(self):
        # 默认目录，作为保底
        self.default_root = Path(getattr(settings.system, "output_dir", "results"))
        self.default_root.mkdir(parents=True, exist_ok=True)

    def _normalize_fields(self, fields):
        if fields:
            raw_fields = fields.split(",") if isinstance(fields, str) else fields
        else:
            raw_fields = settings.search.fields.split(",")

        return [str(field).strip() for field in raw_fields if str(field).strip()]

    def _normalize_row(self, item, column_count: int):
        if isinstance(item, (list, tuple)):
            row = list(item)
        else:
            row = [item]

        row = ["" if cell is None else str(cell) for cell in row]
        if len(row) < column_count:
            row.extend([""] * (column_count - len(row)))
        return row[:column_count]

    def _resolve_final_path(self, filename: str = None, export_format: str = None):
        fmt = (export_format or getattr(settings.system, "export_format", "xlsx")).lower().strip(".")
        if fmt not in self.SUPPORTED_FORMATS:
            raise ValueError(f"不支持的导出格式: {fmt}，仅支持 {', '.join(sorted(self.SUPPORTED_FORMATS))}")

        if not filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"fofa_result_{timestamp}.{fmt}"

        file_path_obj = Path(filename).expanduser()
        if len(file_path_obj.parts) > 1:
            final_path = file_path_obj
        else:
            final_path = self.default_root / file_path_obj

        final_path = final_path.with_suffix(f".{fmt}")
        final_path.parent.mkdir(parents=True, exist_ok=True)
        return final_path, fmt

    def _save_excel(self, data, final_path: Path, headers: list):
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

        data_column_count = len(headers) - 1

        def write_worksheet(sheet_name, rows):
            # 清洗 Sheet 名称 (Excel 不允许 []:*?/\ 且最长31字符)
            clean_name = re.sub(r'[\[\]:*?/\\]', '_', str(sheet_name))
            clean_name = clean_name[:31]

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
                normalized_row = self._normalize_row(item, data_column_count)
                for col_num, cell_data in enumerate(normalized_row, start=1):
                    worksheet.write(row_num, col_num, cell_data, cell_format)

        if isinstance(data, dict):
            for s_name, s_data in data.items():
                if s_data:
                    write_worksheet(s_name, s_data)
            logger.info(f"多 Sheet 合并导出成功 ({len(data)} 个任务)")
        else:
            write_worksheet("FOFA资产", data)

        workbook.close()

    def _save_csv(self, data, final_path: Path, headers: list):
        data_column_count = len(headers) - 1

        with open(final_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)

            if isinstance(data, dict):
                writer.writerow(["QUERY"] + headers)
                exported_count = 0
                for query_name, rows in data.items():
                    if not rows:
                        continue
                    exported_count += 1
                    for row_num, item in enumerate(rows, start=1):
                        normalized_row = self._normalize_row(item, data_column_count)
                        writer.writerow([query_name, row_num] + normalized_row)
                logger.info(f"CSV 合并导出成功 ({exported_count} 个任务)")
            else:
                writer.writerow(headers)
                for row_num, item in enumerate(data, start=1):
                    normalized_row = self._normalize_row(item, data_column_count)
                    writer.writerow([row_num] + normalized_row)

    def save(self, data, filename: str = None, fields: list = None, export_format: str = None):
        """
        保存查询结果到导出文件 (支持 Excel / CSV、单 Sheet / 多任务合并)

        :param data:
            - 如果是 list: 单 Sheet 模式
            - 如果是 dict: 多 Sheet 模式, 格式 {"SheetName": [rows], ...}
        :param filename: 文件名
        :param fields: 表头字段列表
        :param export_format: 导出格式，支持 xlsx / csv
        """
        if not data:
            logger.warning("没有数据需要保存，跳过导出")
            return None

        try:
            final_path, export_format = self._resolve_final_path(filename, export_format)
            field_list = self._normalize_fields(fields)
            headers = ["ID"] + [f.upper() for f in field_list]

            if export_format == "csv":
                self._save_csv(data, final_path, headers)
            else:
                self._save_excel(data, final_path, headers)

            logger.info(f"{export_format.upper()} 已保存至: {final_path}")
            return final_path

        except Exception as e:
            logger.error(f"导出保存失败: {e}")
            return None
