"""AI 助手文本/数据清洗与解析辅助（从 app.py 抽出，无 Streamlit 依赖）。

处理 LLM 回答中的乱码、markdown 表格、SQL 标签，以及把查询结果
解析成图表可用的 DataFrame。仅依赖 re / datetime / decimal / pandas / clean_sql。
"""
import datetime
import decimal
import re

import pandas as pd

from backend.utils.text_cleaner import clean_sql


def parse_data_from_answer(answer: str) -> pd.DataFrame | None:
    if not answer or not isinstance(answer, str):
        return None

    rows = []

    # 模式1：商品编号/平台 + 数值（最精确，优先匹配）
    # 匹配 "商品编号: PR000385 销售额: 481182" 或 "APP: 201单" 等
    patterns = [
        # 商品编号 PRxxxxx + 金额
        r'(?:^|\n|[-•|])\s*(PR\d{4,})[^\d]*(\d[\d,]*\.?\d*)',
        # 商品编号: xxx 格式
        r'(?:商品编号|产品编号|product_id)[^\w]*(PR\d+)[^\d]*(\d[\d,]*\.?\d*)',
        # 平台类型 + 数值
        r'(APP|微信公众号|网站|web|小程序|公众号)[^\d]{0,10}(\d[\d,]*\.?\d*)',
        # 中文键名: 值
        r'[-•|]\s*([^\d:：\n]{2,20}?)[：:]\s*([￥¥$]?\s*[\d,]+\.?\d*)',
        # 纯 key: value
        r'(\w+)\s*[：:]\s*([￥¥$]?\s*[\d,]+\.?\d*)\s*(?:元|单|%|)?',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, answer, re.IGNORECASE | re.MULTILINE)
        if matches and len(matches) >= 2:
            for match in matches:
                key = match[0].strip()
                value_str = re.sub(r'[^\d.]', '', match[1])
                try:
                    value = float(value_str) if value_str else None
                    if value is not None and value > 0 and not _is_garbled_key(key):
                        rows.append({'name': key, 'value': value})
                except (ValueError, TypeError):
                    continue
            if len(rows) >= 2:
                rows = _filter_outlier_rows(rows)
                if len(rows) >= 2:
                    return pd.DataFrame(rows)

    # 模式2：从上下文中提取（带关键词的数值）
    number_pattern = r'([\d,]+\.?\d*)\s*(?:元|单|%|)'
    all_numbers = re.findall(number_pattern, answer)

    if len(all_numbers) >= 3:
        keywords = ['PR', 'APP', '微信', '商品', '平台']
        for kw in keywords:
            if kw in answer:
                context_matches = re.findall(rf'({kw}[^0-9\n]*?)(?:[:：]?\s*)?({number_pattern})', answer, re.IGNORECASE)
                if context_matches and len(context_matches) >= 2:
                    for cm in context_matches:
                        try:
                            val = float(re.sub(r'[^\d.]', '', cm[1]))
                            label = cm[0].strip()
                            # 清理标签：去掉无意义的修饰词
                            label = re.sub(r'^(及|对应|的|为|是|有|共)\s*', '', label)
                            label = label[:30] if len(label) > 30 else label
                            if label and val > 0:
                                rows.append({'name': label, 'value': val})
                        except (ValueError, TypeError):
                            continue
                    if len(rows) >= 2:
                        rows = _filter_outlier_rows(rows)
                        if len(rows) >= 2:
                            return pd.DataFrame(rows)

    return None if not rows else pd.DataFrame(rows)


def _filter_outlier_rows(rows: list[dict]) -> list[dict]:
    """过滤远小于其他数值的离群小值（例如从"3个"中误抓到的"1"），避免
    图表上出现毫无意义的单像素柱和误导性的"1"标签。"""
    if len(rows) < 2:
        return rows
    values = [r['value'] for r in rows]
    max_val = max(values)
    if max_val <= 0:
        return rows
    threshold = max_val * 0.05
    return [r for r in rows if r['value'] >= threshold]


def _is_garbled_key(key: str) -> bool:
    """判断解析到的 key 是否是乱码（Java 对象引用、Python repr、driver 内部类型等），
    避免这些内容被当成图表标签或表格列名展示给用户。"""
    if not key:
        return True
    if re.search(r'[a-zA-Z_][\w.]*@[0-9a-f]{6,8}', key):
        return True
    if re.search(r'\b(?:com|org|net|io|java)\.[a-zA-Z][\w.]*', key):
        return True
    if re.search(r"<class\s+['\"]", key):
        return True
    if re.search(r"^[\[\{]|[\]\}]$", key):
        return True
    # 纯 driver 内部类型名/对象引用（区分于合法列名 orders/users/sales）
    if re.search(r'\b(?:KBObjectField|JDBC|ResultSet)\b', key):
        return True
    if re.search(r'^\d+\s*rows?(?:\s|$)', key, re.IGNORECASE):
        return True
    return False


def clean_sql_local(sql: str) -> str:
    """兼容旧调用：自动剥除 HTML 标签。"""
    return clean_sql(sql, strip_html=True)


def strip_markdown_tables(text: str) -> str:
    """剥离 markdown 表格（含表头分隔线 |---|），避免 LLM 生成的预填充表格
    （如带"待查询结果填充"占位符的表格）与系统真实数据表格重复显示。"""
    if not text:
        return text
    # 匹配以 | 开头的连续多行表格（含对齐分隔行 |---|、|:---:| 等）
    text = re.sub(
        r'(?:^|\n)[ \t]*\|[^\n]*\|(?:[ \t]*\n[ \t]*\|[-:\s|]+\|)?'
        r'(?:[ \t]*\n[ \t]*\|[^\n]*\|)*',
        '\n',
        text,
    )
    # 清理可能残留的多余空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# 不可读的"乱码"内容特征：Java 对象引用、Python repr 调试输出、driver 内部类型名
GARBLED_PATTERNS = [
    # Java toString 输出：com.kingbase8.util.KBObjectField@7c0a2f2b
    r'[a-zA-Z_][\w.]*@[0-9a-f]{6,8}',
    # Java/Kotlin 类的全限定名（含包路径）
    r'(?:^|\s)(?:com|org|net|io|java)\.[a-zA-Z][\w.]*(?:\s|$|[,;:|])',
    # Python repr：<class 'list'>、<sqlalchemy...>
    r"<class\s+['\"][\w.]+['\"]>",
    r"<sqlalchemy\.[\w.]+(\.[\w]+)?\s+object",
    # Python 列表/字典 repr：['orders']、{'key': 'value'}
    r"\[\s*'[^']*'\s*\]",
    r"\{\s*'[^']*'\s*:\s*'[^']*'\s*\}",
    # 内部 driver 错误/类型提示
    r"\d+\s*rows?\s*(?:affected|returned)?",
    r"KBObjectField|JDBC|ResultSet",
    # 行内"占位符"型描述
    r"待查询结果填充|查询结果填充|待补充|待填充",
]


def strip_garbled_content(text: str) -> str:
    """剥离 LLM 回答中误带的数据库对象引用、Python repr 调试输出等不可读内容。
    这些通常是 LLM 直接复制 SQL 工具 observation（如 KingbaseES JDBC 返回的
    Java 对象 toString、SQLAlchemy 内部 repr）导致的，需要在渲染前清除。"""
    if not text:
        return text

    # 1. 按行扫描：包含乱码特征词的整行直接删除
    cleaned_lines = []
    for line in text.splitlines():
        if any(re.search(pat, line) for pat in GARBLED_PATTERNS):
            continue
        cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)

    # 2. 清理行内的乱码片段（保留行，去掉乱码）
    for pat in GARBLED_PATTERNS:
        text = re.sub(pat, '', text)

    # 3. 清理可能残留的多余空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _convert_value(val):
    """将 SQLAlchemy 返回的原始值转换为 DataFrame 友好的 Python 原生类型。
    处理 datetime/Decimal/bytes/UUID 等特殊类型，避免后续处理时类型不一致。"""
    if val is None:
        return None
    if isinstance(val, datetime.datetime):
        return val.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(val, datetime.date):
        return val.strftime('%Y-%m-%d')
    if isinstance(val, datetime.time):
        return val.strftime('%H:%M:%S')
    if isinstance(val, datetime.timedelta):
        return val.total_seconds()
    if isinstance(val, decimal.Decimal):
        return float(val)
    if isinstance(val, bytes):
        try:
            return val.decode('utf-8')
        except UnicodeDecodeError:
            return val.hex()
    if isinstance(val, (set, frozenset)):
        return list(val)
    return val
