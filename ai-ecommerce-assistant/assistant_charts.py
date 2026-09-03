"""AI 助手图表生成辅助（从 app.py 抽出，无 Streamlit 依赖，便于单测）。

仅依赖 pandas / plotly，不触发任何 RAG 或数据库初始化。
"""
import re

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def detect_chart_type(df: pd.DataFrame, question: str = "") -> str:
    if df is None or len(df) == 0 or len(df.columns) < 2:
        return "none"
    
    col1, col2 = df.columns[0], df.columns[1]
    
    try:
        pd.to_numeric(df[col2], errors='raise')
    except (ValueError, TypeError):
        return "none"
    
    question_lower = question.lower()
    col1_lower = col1.lower()
    col2_lower = col2.lower() if col2 else ""
    
    rank_keywords = ['top', '最高', '排名', '排行', r'前\d+', '销量最高', '销售额最高']
    if any(re.search(k, question_lower) for k in rank_keywords):
        return "bar"
    
    compare_keywords = ['哪个', '谁', '比较', '对比', 'vs', '更多', '更高', '更低', '差异']
    if any(k in question_lower for k in compare_keywords):
        return "bar"
    
    rate_keywords = ['退款率', '转化率', '点击率', '复购率', 'rate', 'ratio', '比例对比', '各.*率']
    if any(k in question_lower for k in rate_keywords) or \
       (any(k in col2_lower for k in ['rate', 'ratio', '率']) and len(df) > 2):
        return "bar_h"
    
    first_col_str = df[col1].astype(str)
    
    is_date_format = first_col_str.str.match(r'^\d{4}-\d{2}-\d{2}').any() or \
                     first_col_str.str.match(r'^\d{2}/\d{2}').any() or \
                     (first_col_str.str.contains(r'^(0?[1-9]|1[0-9]|2[0-3])$', regex=True).any() and len(df) >= 12)
    
    time_col_names = ['date', '时间', 'time', 'hour', 'weekday', '星期', 'month', '月', 'order_date', 'order_hour']
    
    time_keywords = ['每天', '每日', '趋势', '变化', '时间段', '24小时', '最近', '周', '月份']
    if is_date_format or \
       (any(k in col1_lower for k in time_col_names)) or \
       (any(k in question_lower for k in time_keywords) and not any(k in question_lower for k in ['top', '最高'])):
        return "line"
    
    share_keywords = ['占比', '份额', '构成', '组成', '分布情况', 'percent of total']
    if any(k in question_lower for k in share_keywords) and len(df) <= 8:
        return "pie"
    
    if len(df) <= 4:
        return "pie"
    
    return "bar"


_CHART_SEQUENCE = ["#1565C0", "#14B8A6", "#F97316", "#8B5CF6", "#64748B"]
_CHART_FONT = {
    "family": "Manrope, Noto Sans SC, Microsoft YaHei, sans-serif",
    "size": 13,
    "color": "#334155",
}
_CHART_HOVERLABEL = {
    "bgcolor": "#0F172A",
    "bordercolor": "#0F172A",
    "font": {
        "family": "Manrope, Noto Sans SC, Microsoft YaHei, sans-serif",
        "size": 12,
        "color": "#F8FAFC",
    },
}


def create_chart(df: pd.DataFrame, title: str = "", question: str = "") -> go.Figure | None:
    chart_type = detect_chart_type(df, question)
    
    if chart_type == "none":
        return None

    cols = df.columns.tolist()
    x_col, y_col = cols[0], cols[1]

    if not title or title == "undefined" or not title.strip():
        title = f"{y_col} 分析"

    if chart_type == "line":
        fig = px.line(df, x=x_col, y=y_col, template="plotly_white", title=title,
                      markers=True, color_discrete_sequence=[_CHART_SEQUENCE[0]])
        fig.update_traces(line_width=3, marker_size=8,
                          fill='tozeroy', fillcolor='rgba(21,101,192,0.08)')
        fig.add_scatter(x=df[x_col], y=df[y_col], mode='markers',
                        marker={"size": 9, "color": _CHART_SEQUENCE[1], "line": {"width": 2, "color": '#FFFFFF'}},
                        showlegend=False)

    elif chart_type == "pie":
        fig = px.pie(df, names=x_col, values=y_col, template="plotly_white", title=title,
                     hole=0.42, color_discrete_sequence=_CHART_SEQUENCE)
        fig.update_traces(textposition='inside', textinfo='percent+label',
                          textfont={"size": 12, "color": '#0F172A'},
                          hovertemplate='<b>%{label}</b><br>数值: %{value:,.2f}<br>占比: %{percent}<extra></extra>',
                          pull=[0.015] * len(df))

    elif chart_type in ["bar_h", "bar"]:
        df_plot = df.copy()

        try:
            df_plot[y_col] = pd.to_numeric(df_plot[y_col], errors='coerce')
        except Exception:
            pass

        if len(df_plot) > 8:
            df_plot = df_plot.nlargest(8, columns=y_col).reset_index(drop=True)

        n_items = len(df_plot)
        # 受控蓝青色板：高值用主蓝，低值逐步降为浅蓝，避免高饱和红色误导风险语义。
        bar_colors = ['#1565C0', '#1E88E5', '#42A5F5', '#64B5F6',
                      '#90CAF9', '#BBDEFB', '#D6E8FB', '#EAF3FC']

        def format_y_label(val):
            val_str = str(val).strip()
            if val_str.isdigit():
                hour_val = int(val_str)
                if 0 <= hour_val <= 23:
                    return f"{hour_val}时"
                elif hour_val >= 1 and hour_val <= 31:
                    return f"{hour_val}日"
            return val_str

        # 计算合适的图表高度：每项至少 85px + 标题区 + 边距，让条形更显著
        dynamic_height = max(550, 140 + n_items * 85)

        if chart_type == "bar_h":
            fig = go.Figure()
            for i in range(n_items):
                y_val = df_plot[y_col].iloc[i]
                x_raw = df_plot[x_col].iloc[i]
                x_label = format_y_label(x_raw)
                try:
                    y_num = float(y_val)
                    y_text = f'{y_num:,.0f}'
                except (ValueError, TypeError):
                    y_num = 0
                    y_text = str(y_val)

                fig.add_trace(go.Bar(
                    x=[y_num],
                    y=[x_label],
                    orientation='h',
                    name=x_label,
                    marker={
                        "color": bar_colors[i % len(bar_colors)],
                        "line": {"width": 0, "color": 'rgba(255,255,255,0)'},
                        "cornerradius": 4,
                    },
                    text=y_text,
                    textposition='outside',
                    textfont={"size": 13, "color": '#334155', "family": 'JetBrains Mono, monospace'},
                    hovertemplate=f'<b>{x_label}</b><br>%{{x:,.0f}}<extra></extra>',
                ))

            fig.update_layout(height=dynamic_height, barmode='group')

        else:
            df_sorted = df_plot.sort_values(by=y_col, ascending=True).reset_index(drop=True)
            fig = go.Figure()
            for i in range(n_items):
                y_val = df_sorted[y_col].iloc[i]
                x_raw = df_sorted[x_col].iloc[i]
                x_label = format_y_label(x_raw)
                try:
                    y_num = float(y_val)
                    y_text = f'{y_num:,.0f}'
                except (ValueError, TypeError):
                    y_num = 0
                    y_text = str(y_val)

                fig.add_trace(go.Bar(
                    x=[y_num],
                    y=[x_label],
                    orientation='h',
                    name=x_label,
                    marker={
                        "color": bar_colors[(n_items - 1 - i) % len(bar_colors)],
                        "line": {"width": 0, "color": 'rgba(255,255,255,0)'},
                        "cornerradius": 4,
                    },
                    text=y_text,
                    textposition='outside',
                    textfont={"size": 13, "color": '#334155', "family": 'JetBrains Mono, monospace'},
                    hovertemplate=f'<b>{x_label}</b><br>%{{x:,.0f}}<extra></extra>',
                ))

            fig.update_layout(height=dynamic_height, barmode='group')

    else:
        fig = go.Figure()

    fig.update_layout(
        title={"text": title, "x": 0.02, "xanchor": 'left', "y": 0.97, "yanchor": 'top',
                   "font": {"size": 17, "color": '#0F172A', "family": _CHART_FONT["family"]}},
        margin={"l": 80 if chart_type in ["bar_h", "bar"] else 30,
                    "r": 100 if chart_type in ["bar_h", "bar"] else 30,
                    "t": 70, "b": 50},
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='#FFFFFF',
        font=_CHART_FONT,
        hoverlabel=_CHART_HOVERLABEL,
        colorway=_CHART_SEQUENCE,
        showlegend=False,
        xaxis={
            "showgrid": False if chart_type in ["bar_h", "bar"] else True,
            "gridcolor": '#E2E8F0',
            "linecolor": '#CBD5E1',
            "zerolinecolor": '#CBD5E1',
            "showticklabels": False if chart_type in ["bar_h", "bar"] else True,
            "tickangle": -20 if chart_type == "line" else 0,
            "tickfont": {"size": 11, "color": '#64748B'},
            "zeroline": False,
            "range": [0, None] if chart_type in ["bar_h", "bar"] else None,
        },
        yaxis={
            "showgrid": True,
            "gridcolor": '#E2E8F0',
            "linecolor": '#CBD5E1',
            "zerolinecolor": '#CBD5E1',
            "tickfont": {"size": 11, "color": '#64748B'},
        },
        hovermode='closest',
        bargap=0.42,
    )

    return fig
