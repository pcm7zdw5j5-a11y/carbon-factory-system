import csv
import io
import re
import zipfile
from xml.etree import ElementTree as ET


HEADER_ALIASES = {
    "order_no": ["订单编号", "订单号", "主订单编号", "子订单编号", "淘宝订单编号"],
    "customer_name": ["客户", "客户名称", "买家昵称", "买家会员名", "收货人", "收件人"],
    "customer_contact": ["手机号", "手机", "联系电话", "收货人手机", "收件人手机", "电话"],
    "product_name": ["商品", "商品名称", "商品标题", "宝贝标题", "宝贝名称"],
    "quantity": ["数量", "购买数量", "宝贝总数量", "件数"],
    "final_quote": ["金额", "实付金额", "买家实际支付金额", "订单金额", "付款金额", "应付金额"],
    "notes": ["备注", "买家留言", "卖家备注", "订单备注", "留言"],
}


def normalize_header(value):
    return re.sub(r"[\s:：()（）\[\]【】]", "", str(value or "")).lower()


def clean_cell(value):
    return str(value or "").strip()


def match_header(headers, aliases):
    normalized_headers = [normalize_header(header) for header in headers]
    for alias in aliases:
        normalized_alias = normalize_header(alias)
        for index, header in enumerate(normalized_headers):
            if header == normalized_alias or normalized_alias in header:
                return index
    return None


def rows_to_records(rows):
    rows = [[clean_cell(cell) for cell in row] for row in rows if any(clean_cell(cell) for cell in row)]
    if not rows:
        return []
    headers = rows[0]
    mapping = {field: match_header(headers, aliases) for field, aliases in HEADER_ALIASES.items()}
    records = []
    for row in rows[1:]:
        record = {}
        for field, index in mapping.items():
            record[field] = row[index] if index is not None and index < len(row) else ""
        if any(record.values()):
            records.append(record)
    return records


def decode_upload_bytes(data):
    for encoding in ("utf-8-sig", "gb18030", "gbk"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def parse_csv(file_obj, delimiter=None):
    data = file_obj.read()
    text = decode_upload_bytes(data)
    sample = text[:2048]
    if delimiter is None:
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = "\t" if "\t" in sample else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    return rows_to_records(list(reader))


def parse_shared_strings(root):
    namespace = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    strings = []
    for item in root.findall("a:si", namespace):
        parts = [node.text or "" for node in item.findall(".//a:t", namespace)]
        strings.append("".join(parts))
    return strings


def column_index(cell_ref):
    letters = re.sub(r"[^A-Z]", "", cell_ref.upper())
    index = 0
    for letter in letters:
        index = index * 26 + ord(letter) - ord("A") + 1
    return max(index - 1, 0)


def parse_xlsx(file_obj):
    namespace = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(file_obj) as workbook:
        shared_strings = []
        if "xl/sharedStrings.xml" in workbook.namelist():
            shared_root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
            shared_strings = parse_shared_strings(shared_root)

        sheet_names = sorted(
            name for name in workbook.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
        )
        if not sheet_names:
            return []
        sheet_root = ET.fromstring(workbook.read(sheet_names[0]))

    rows = []
    for row in sheet_root.findall(".//a:sheetData/a:row", namespace):
        values = []
        for cell in row.findall("a:c", namespace):
            cell_ref = cell.attrib.get("r", "")
            index = column_index(cell_ref) if cell_ref else len(values)
            while len(values) <= index:
                values.append("")

            cell_type = cell.attrib.get("t")
            if cell_type == "inlineStr":
                text_node = cell.find(".//a:t", namespace)
                value = text_node.text if text_node is not None else ""
            else:
                value_node = cell.find("a:v", namespace)
                value = value_node.text if value_node is not None else ""
                if cell_type == "s" and value not in ("", None):
                    shared_index = int(float(value))
                    value = shared_strings[shared_index] if shared_index < len(shared_strings) else ""
            values[index] = clean_cell(value)
        rows.append(values)
    return rows_to_records(rows)


def read_taobao_order_file(file_storage):
    filename = (file_storage.filename or "").lower()
    if filename.endswith(".xlsx"):
        return parse_xlsx(file_storage.stream)
    if filename.endswith(".csv"):
        return parse_csv(file_storage.stream)
    if filename.endswith(".tsv") or filename.endswith(".txt"):
        return parse_csv(file_storage.stream, delimiter="\t")
    raise ValueError("请上传 .xlsx、.csv 或 .tsv 格式的淘宝订单文件。")
