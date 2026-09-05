"""_highlight_answer 纯函数测试：HTML 实体 / 行内代码 / 代码块中的数字不被高亮破坏。

import app 会触发 Streamlit 页面脚本执行，但 _highlight_answer 本身不调用 st.*，
且 test_lazy_rag.py 已证明冷导入不会拉起重依赖；这里复用同一导入前提。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

pytest.importorskip("streamlit")
import app  # noqa: E402


def test_html_entities_survive_number_highlight():
    """html.escape 把撇号转成 &#x27;，其中数字 27 曾被高亮正则包进 span，
    实体被破坏后页面渲染出乱码。"""
    out = app._highlight_answer("it's a 3.5% increase")
    assert "&#x27;" in out, "HTML 实体必须原样保留"
    assert "&#x<span" not in out, "实体内部的数字不得被高亮包裹"
    assert '<span class="highlight-num">3.5%</span>' in out


def test_inline_code_numbers_not_highlighted():
    out = app._highlight_answer("执行 `SELECT 1` 后共 2 条结果")
    assert "`SELECT 1`" in out, "行内代码应原样保留"
    assert "SELECT <span" not in out
    assert '<span class="highlight-num">2</span>' in out


def test_code_block_numbers_not_highlighted():
    answer = "看示例：\n```sql\nSELECT TOP 3 FROM orders\n```\n共 3 条记录"
    out = app._highlight_answer(answer)
    assert "SELECT TOP 3 FROM orders" in out, "代码块内容必须原样保留"
    assert "highlight-num" not in out.split("```")[1], "代码块内不得出现高亮 span"
    assert '<span class="highlight-num">3</span>' in out, "代码块外的数字正常高亮"


def test_plain_numbers_still_highlighted():
    out = app._highlight_answer("销售额 481182 元，占比 35%")
    assert '<span class="highlight-num">481182</span>' in out
    assert '<span class="highlight-num">35%</span>' in out
