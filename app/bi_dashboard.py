import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os

# 页面配置
st.set_page_config(
    page_title="电商数据 BI 看板",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 标题
st.title("🛒 电商订单数据分析看板")
st.markdown("---")

# 加载数据（使用缓存加速）
@st.cache_data
def load_data():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(script_dir, '..', 'data', 'cleaned_orders.csv')
    df = pd.read_csv(
        data_path,
        parse_dates=['下单时间', '付款时间']
    )
    df['平台类型'] = df['平台类型'].replace({'AP': 'APP', 'Web': 'Web网站'})
    return df

try:
    df = load_data()
    st.success(f"✅ 成功加载 {len(df):,} 条订单数据")
except Exception as e:
    st.error(f"❌ 数据加载失败：{e}")
    st.stop()

# ========== 侧边栏筛选器 ==========
st.sidebar.header("🔍 筛选条件")

# 平台筛选
platforms = st.sidebar.multiselect(
    "选择平台 *",
    options=df['平台类型'].unique(),
    default=df['平台类型'].unique(),
    placeholder="请至少选择一个平台"
)

if len(platforms) == 0:
    st.sidebar.error("⚠️ 请至少选择一个平台")

# 日期范围
min_date = df['下单时间'].min().date()
max_date = df['下单时间'].max().date()

date_range = st.sidebar.date_input(
    "选择日期范围",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

# 应用筛选
if len(date_range) == 2:
    start_date, end_date = date_range
    mask = (
        (df['平台类型'].isin(platforms)) &
        (df['下单时间'].dt.date >= start_date) &
        (df['下单时间'].dt.date <= end_date)
    )
    filtered_df = df[mask].copy()
else:
    filtered_df = df[df['平台类型'].isin(platforms)].copy()

# ========== 核心指标卡 ==========
st.subheader("📊 核心指标")

has_data = len(filtered_df) > 0

total_sales = filtered_df['付款金额'].sum() if has_data else 0
total_orders = filtered_df['订单号'].nunique() if has_data else 0
total_users = filtered_df['用户名'].nunique() if has_data else 0
unique_days = len(filtered_df['下单时间'].dt.date.unique()) if has_data else 0

avg_order_value = total_sales / total_orders if total_orders > 0 else 0

if has_data and total_users > 0:
    user_order_counts = filtered_df.groupby('用户名')['订单号'].nunique()
    repeat_users = (user_order_counts > 1).sum()
    repeat_rate = repeat_users / total_users * 100
else:
    repeat_users = 0
    repeat_rate = 0

refund_count = (filtered_df['是否退款'] == '是').sum() if has_data else 0
refund_rate = refund_count / total_orders * 100 if total_orders > 0 else 0

overall_avg = df['付款金额'].mean()

col1, col2, col3 = st.columns(3)

if has_data and unique_days > 0:
    daily_avg = f"日均 ¥{total_sales/unique_days:,.0f}"
else:
    daily_avg = None

col1.metric(
    label="💰 总销售额",
    value=f"¥{total_sales:,.0f}" if has_data else "-",
    delta=daily_avg
)

col2.metric(
    label="📦 总订单数",
    value=f"{total_orders:,}" if has_data else "-",
    delta=f"人均 {total_orders/total_users:.1f} 单" if has_data and total_users > 0 else None
)

col3.metric(
    label="👥 活跃用户",
    value=f"{total_users:,}" if has_data else "-",
    delta=f"占全量 {total_users/df['用户名'].nunique()*100:.1f}%" if has_data and df['用户名'].nunique() > 0 else None
)

col4, col5, col6 = st.columns(3)

if has_data and total_orders > 0:
    delta_color = "normal" if avg_order_value >= overall_avg else "inverse"
    price_delta = f"较全站均值{'↑' if avg_order_value >= overall_avg else '↓'}{abs(avg_order_value-overall_avg)/overall_avg*100:.1f}%"
else:
    delta_color = "off"
    price_delta = None

col4.metric(
    label="💵 客单价",
    value=f"¥{avg_order_value:,.0f}" if has_data and total_orders > 0 else "-",
    delta=price_delta,
    delta_color=delta_color
)

col5.metric(
    label="🔄 复购率",
    value=f"{repeat_rate:.1f}%" if has_data else "-",
    delta=f"{repeat_users:,} 人复购" if has_data else None
)

col6.metric(
    label="↩️ 退款率",
    value=f"{refund_rate:.2f}%" if has_data else "-",
    delta=f"{refund_count:,} 笔退款" if has_data else None,
    delta_color="inverse"
)

st.markdown("---")

# ========== 图表区域 ==========
# 第一行：每日销售趋势 + 平台占比
st.subheader("📈 每日销售趋势")
col_chart1, col_chart2 = st.columns([2, 1])

with col_chart1:
    daily_sales = filtered_df.groupby(filtered_df['下单时间'].dt.date)['付款金额'].sum().reset_index()
    daily_sales.columns = ['日期', '销售额']
    
    if len(daily_sales) > 0:
        fig_line = px.line(
            daily_sales,
            x='日期',
            y='销售额',
            markers=True,
            template="plotly_white"
        )
        fig_line.update_traces(
            line=dict(width=2.5, color='#00d4ff'),
            marker=dict(size=6, color='#00d4ff')
        )
        
        max_idx = daily_sales['销售额'].idxmax()
        max_date = daily_sales.loc[max_idx, '日期']
        max_sales = daily_sales.loc[max_idx, '销售额']
        
        fig_line.add_annotation(
            x=max_date,
            y=max_sales,
            text=f"峰值: ¥{max_sales:,.0f}",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=2,
            arrowcolor='#ff6b6b',
            ax=40,
            ay=-40,
            font=dict(size=11, color='#ff6b6b')
        )
        
        fig_line.update_layout(
            hovermode='x unified',
            xaxis=dict(
                tickformat='%Y-%m-%d',
                tickangle=45
            ),
            plot_bgcolor='rgba(0,0,0,0.03)'
        )
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.warning("⚠️ 当前筛选条件下无数据")

with col_chart2:
    platform_sales = filtered_df.groupby('平台类型')['付款金额'].sum().reset_index()
    total_platform_sales = platform_sales['付款金额'].sum()
    platform_sales['占比'] = platform_sales['付款金额'] / total_platform_sales * 100
    
    major_platforms = platform_sales[platform_sales['占比'] >= 3].copy()
    minor_platforms = platform_sales[platform_sales['占比'] < 3].copy()
    
    if len(minor_platforms) > 0:
        other_sales = minor_platforms['付款金额'].sum()
        other_row = pd.DataFrame({
            '平台类型': ['其他'],
            '付款金额': [other_sales],
            '占比': [other_sales / total_platform_sales * 100]
        })
        major_platforms = pd.concat([major_platforms, other_row], ignore_index=True)
    
    fig_pie = px.pie(
        major_platforms,
        values='付款金额',
        names='平台类型',
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    fig_pie.update_traces(
        textposition='outside',
        textinfo='percent+label',
        textfont=dict(size=11)
    )
    fig_pie.update_layout(
        showlegend=True,
        margin=dict(t=60, b=60, l=60, r=80)
    )
    st.plotly_chart(fig_pie, use_container_width=True)

# 第二行：24小时下单分布 + RFM 用户分层
st.subheader("⏰ 用户行为分析")
col_time, col_rfm = st.columns(2)

with col_time:
    hourly_orders = filtered_df.groupby(filtered_df['下单时间'].dt.hour)['订单号'].nunique().reset_index()
    hourly_orders.columns = ['小时', '订单数']
    
    fig_hour = px.bar(
        hourly_orders,
        x='小时',
        y='订单数',
        color='订单数',
        color_continuous_scale='Blues'
    )
    fig_hour.update_layout(
        title="24小时下单分布",
        xaxis_title="小时",
        yaxis_title="订单数",
        xaxis=dict(
            tickmode='array',
            tickvals=[0, 6, 12, 18, 23],
            ticktext=['0点', '6点', '12点', '18点', '23点']
        ),
        showlegend=False
    )
    fig_hour.update_traces(showlegend=False)
    st.plotly_chart(fig_hour, use_container_width=True)

with col_rfm:
    user_rfm = filtered_df.groupby('用户名').agg({
        '下单时间': lambda x: (filtered_df['下单时间'].max() - x.max()).days,
        '订单号': 'nunique',
        '付款金额': 'sum'
    }).reset_index()
    user_rfm.columns = ['用户名', 'R', 'F', 'M']
    
    def rfm_segment(row):
        if row['R'] <= 30 and row['F'] >= 2 and row['M'] >= 2000:
            return '重要价值用户'
        elif row['R'] <= 30 and row['F'] >= 2:
            return '重要发展用户'
        elif row['R'] > 180 and row['M'] >= 2000:
            return '重要保持用户'
        elif row['R'] > 180 and row['F'] == 1:
            return '流失用户'
        else:
            return '一般用户'
    
    user_rfm['用户分层'] = user_rfm.apply(rfm_segment, axis=1)
    rfm_counts = user_rfm['用户分层'].value_counts().reset_index()
    rfm_counts.columns = ['用户分层', '人数']
    
    segment_order = ['重要价值用户', '重要发展用户', '重要保持用户', '一般用户', '流失用户']
    rfm_counts['用户分层'] = pd.Categorical(rfm_counts['用户分层'], categories=segment_order, ordered=True)
    rfm_counts = rfm_counts.sort_values('用户分层')
    
    total_rfm = rfm_counts['人数'].sum()
    
    fig_rfm = px.pie(
        rfm_counts,
        values='人数',
        names='用户分层',
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    
    fig_rfm.update_traces(
        textposition='outside',
        textinfo='percent+label',
        textfont=dict(size=11)
    )
    
    fig_rfm.update_layout(
        showlegend=True,
        margin=dict(t=60, b=60, l=60, r=80)
    )
    st.plotly_chart(fig_rfm, use_container_width=True)
    
    churn_rate = rfm_counts[rfm_counts['用户分层'] == '流失用户']['人数'].sum() / rfm_counts['人数'].sum() * 100
    
    if churn_rate < 5:
        insight = f"💡 用户留存极佳（流失率仅 {churn_rate:.1f}%），建议通过会员权益维持活跃度"
    elif churn_rate < 20:
        insight = f"💡 流失用户占比 {churn_rate:.1f}%，建议通过优惠券激活召回"
    else:
        insight = f"⚠️ 流失用户占比高达 {churn_rate:.1f}%，需紧急启动召回营销活动"
    
    st.info(insight)

# 第三行：商品 TOP10 + 用户 TOP10
col_product, col_user = st.columns(2)

with col_product:
    st.subheader("🏆 商品销售额 TOP10")
    top_products = filtered_df.groupby('商品编号')['付款金额'].sum().nlargest(10).reset_index()
    
    fig_bar = px.bar(
        top_products,
        x='商品编号',
        y='付款金额',
        color='付款金额',
        color_continuous_scale='Reds'
    )
    fig_bar.update_layout(
        xaxis_title="商品编号",
        yaxis_title="销售额 (元)",
        yaxis=dict(ticksuffix="元"),
        coloraxis_colorbar=dict(title="销售额 (元)"),
        xaxis_tickangle=-30
    )
    fig_bar.update_traces(
        texttemplate='%{y:,.0f}元',
        textposition='outside',
        hovertemplate='商品: %{x}<br>销售额: ¥%{y:,.0f}<extra></extra>'
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with col_user:
    st.subheader("👑 用户消费 TOP10")
    top_users = filtered_df.groupby('用户名')['付款金额'].sum().nlargest(10).reset_index()
    
    fig_user = px.bar(
        top_users,
        x='付款金额',
        y='用户名',
        orientation='h',
        color='付款金额',
        color_continuous_scale='Viridis'
    )
    fig_user.update_layout(
        xaxis_title="消费金额 (元)",
        yaxis_title="用户",
        xaxis=dict(ticksuffix="元"),
        coloraxis_colorbar=dict(title="消费金额 (元)"),
        margin=dict(t=30, b=30, l=100, r=150),
        bargroupgap=0.1
    )
    fig_user.update_traces(
        texttemplate='%{x:,.0f}',
        textposition='outside',
        cliponaxis=False
    )
    st.plotly_chart(fig_user, use_container_width=True)

# 底部信息
st.markdown("---")
st.caption(f"数据更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 数据来源：cleaned_orders.csv")