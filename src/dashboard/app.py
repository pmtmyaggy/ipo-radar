"""IPO Radar 仪表盘 - Streamlit应用入口.

提供可视化界面展示所有分析结果。
"""

from datetime import date, timedelta
from typing import cast

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.crawler.api import CrawlerAPI
from src.crawler.models.schemas import CompositeReport, StockBar
from src.radar.monitor import IPORadar
from src.scorer.composite import SignalAggregator
from src.scorer.daily_scan import DailyScanner

# 页面配置
st.set_page_config(
    page_title="IPO Radar - IPO决策信息系统",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 自定义CSS样式
def apply_custom_styles() -> None:
    """应用自定义CSS样式."""
    st.markdown("""
    <style>
    :root {
        --bg-color: #0f1117;
        --card-bg: #111827;
        --border-color: #1e293b;
    }
    
    .main {
        background-color: var(--bg-color);
    }
    
    /* 信号颜色 */
    .signal-strong {
        color: #00ff88;
        font-weight: bold;
    }
    .signal-opportunity {
        color: #3b82f6;
        font-weight: bold;
    }
    .signal-watch {
        color: #f59e0b;
        font-weight: bold;
    }
    .signal-no-action {
        color: #64748b;
    }
    
    /* 卡片样式 */
    .metric-card {
        background-color: var(--card-bg);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }
    
    /* 表格样式 */
    .dataframe {
        font-size: 14px;
    }
    </style>
    """, unsafe_allow_html=True)


# 初始化组件
@st.cache_resource
def get_crawler() -> CrawlerAPI:
    """获取爬虫API（缓存）."""
    return CrawlerAPI()


def get_radar() -> IPORadar:
    """获取雷达."""
    return IPORadar()


def get_aggregator() -> SignalAggregator:
    """获取信号聚合器."""
    return SignalAggregator()


def create_scanner() -> DailyScanner:
    """创建新的扫描器实例.

    不缓存，避免旧会话里保留过期的扫描状态或依赖对象。
    """
    return DailyScanner()


# 侧边栏
def render_sidebar() -> str:
    """渲染侧边栏."""
    with st.sidebar:
        st.title("📡 IPO Radar")
        st.markdown("---")

        # 导航
        page = st.radio(
            "导航",
            ["信号总览", "个股详情", "IPO日历", "观察名单管理"],
        )

        st.markdown("---")

        # 快速操作
        st.subheader("快速操作")

        if st.button("🔄 立即扫描", use_container_width=True):
            with st.spinner("扫描中..."):
                scanner = create_scanner()
                current_result = st.session_state.get('last_scan_result')
                scan_mode = getattr(current_result, "source_mode", "watchlist") if current_result else "watchlist"
                result = scanner.run_scan(mode=scan_mode)
                st.session_state['last_scan_result'] = result
                if result.total_count == 0:
                    st.warning(f"扫描完成，但 {scan_mode} 列表中没有可扫描的标的。")
                else:
                    st.success(
                        f"即时扫描完成！已更新 {result.total_count} 个标的，"
                        f"发现 {result.strong_opportunity_count} 个强烈机会，"
                        f"{result.opportunity_count} 个常规机会。"
                    )

        # 显示上次更新时间
        if 'last_scan_result' in st.session_state:
            last_scan = st.session_state['last_scan_result']
            st.caption(f"最后更新: {last_scan.scanned_at.strftime('%Y-%m-%d %H:%M')}")

        st.markdown("---")

        # 关于
        st.caption("IPO-Radar v0.1.0")
        st.caption("IPO决策信息系统")

    return page


# 主页 - 信号总览
def render_overview() -> None:
    """渲染信号总览页面."""
    st.header("📊 信号总览")

    # 扫描池选择
    target_mode_label = st.radio("选择扫描池：", ["⭐ 观察名单 (Watchlist, 推荐)", "🔍 自动发现 (Discovery, 极新爬虫)"], horizontal=True)
    target_mode = "watchlist" if "Watchlist" in target_mode_label else "discovery"

    # 获取数据
    current_result = st.session_state.get("last_scan_result")
    current_mode = getattr(current_result, "source_mode", None)

    if current_result is None or current_mode != target_mode:
        with st.spinner(f"正在加载 {target_mode} 数据..."):
            scanner = create_scanner()
            result = scanner.run_scan(mode=target_mode)
            st.session_state['last_scan_result'] = result

    result = st.session_state['last_scan_result']

    if result.total_count == 0 and target_mode == "discovery":
        with st.spinner("正在重新同步自动发现 universe..."):
            scanner = create_scanner()
            refreshed_result = scanner.run_scan(mode="discovery")
            if refreshed_result.total_count > 0 or refreshed_result.errors:
                st.session_state['last_scan_result'] = refreshed_result
                result = refreshed_result

    if result.total_count == 0:
        st.warning(f"⚠️  当前 【{target_mode_label}】 扫描列表为空。")

    # 顶部统计卡片
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="🎯 STRONG OPPORTUNITY",
            value=result.strong_opportunity_count,
        )

    with col2:
        st.metric(
            label="📈 OPPORTUNITY",
            value=result.opportunity_count,
        )

    with col3:
        st.metric(
            label="👀 WATCH",
            value=result.watch_count,
        )

    with col4:
        st.metric(
            label="⏰ 即将到期禁售期",
            value=sum(
                1
                for r in result.reports
                if r["windows"].get("lockup_days_until") is not None
                and cast(int, r["windows"].get("lockup_days_until")) <= 14
            ),
        )

    st.markdown("---")

    # 信号表格
    title_text = "观察名单" if target_mode == "watchlist" else "自动发现"
    st.subheader(f"📋 {title_text} 信号详细列表")

    if result.reports:
        # 准备表格数据
        df_data = []
        for report in result.reports:
            company_name = report.get("company_name") or "-"
            price_vs_ipo = report.get("price_vs_ipo")
            df_data.append({
                "股票": report['ticker'],
                "公司": company_name[:20],
                "上市天数": report.get('days_since_ipo', '-'),
                "vs IPO": f"{((price_vs_ipo - 1) * 100):+.1f}%"
                         if price_vs_ipo is not None else '-',
                "活跃窗口": get_active_window_text(dict(report)),
                "综合信号": report['overall_signal'],
                "基本面": report.get('fundamental_score', '-'),
            })

        df = pd.DataFrame(df_data)

        # 添加颜色标记
        def color_signal(val: str) -> str:
            colors = {
                "STRONG_OPPORTUNITY": "color: #00ff88; font-weight: bold",
                "OPPORTUNITY": "color: #3b82f6; font-weight: bold",
                "WATCH": "color: #f59e0b",
                "NO_ACTION": "color: #64748b",
            }
            return colors.get(val, "")

        styled_df = df.style.applymap(color_signal, subset=["综合信号"])

        st.dataframe(
            styled_df,
            use_container_width=True,
            height=400,
        )

        # 选中股票详情
        selected = st.selectbox(
            "查看详情",
            [r['ticker'] for r in result.reports],
            format_func=lambda x: (
                f"{x} - "
                f"{str(next((r.get('company_name') or '' for r in result.reports if r['ticker'] == x), ''))[:30]}"
            ),
        )

        if selected:
            render_stock_detail(selected)
    else:
        st.info("暂无数据，请点击侧边栏的'立即扫描'按钮")


def get_active_window_text(report: dict) -> str:
    """获取活跃窗口文本."""
    windows = report.get('windows', {})

    active_windows = []

    if windows.get('base_detected'):
        if windows.get('breakout_signal'):
            active_windows.append(f"突破({windows['breakout_signal']})")
        else:
            active_windows.append("底部形成")

    if windows.get('lockup_days_until') is not None and windows['lockup_days_until'] <= 14:
        active_windows.append(f"禁售期({windows['lockup_days_until']}天)")

    if windows.get('earnings_days_until') is not None and windows['earnings_days_until'] <= 7:
        active_windows.append(f"财报({windows['earnings_days_until']}天)")

    return ", ".join(active_windows) if active_windows else "-"


# 个股详情
def render_stock_detail(ticker: str | None = None) -> None:
    """渲染个股详情."""
    if ticker is None:
        ticker = st.text_input("输入股票代码", value="CAVA").upper()

    if not ticker:
        return

    st.header(f"📈 {ticker} 详情")

    # 获取报告
    aggregator = get_aggregator()

    with st.spinner(f"正在分析 {ticker}..."):
        report = aggregator.generate_report(ticker)

    # 基本信息
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("当前价格", f"${report.current_price:.2f}" if report.current_price else "N/A")

    with col2:
        if report.price_vs_ipo:
            change = (report.price_vs_ipo - 1) * 100
            st.metric("vs IPO", f"{change:+.1f}%")
        else:
            st.metric("vs IPO", "N/A")

    with col3:
        st.metric("上市天数", report.days_since_ipo if report.days_since_ipo else "N/A")

    with col4:
        st.metric("基本面评分", f"{report.fundamental_score}/100" if report.fundamental_score else "N/A")

    st.markdown("---")

    # K线图
    st.subheader("📊 价格走势")

    try:
        from datetime import date, timedelta
        # 如果没有 IPO 记录，默认查询过去一年的数据
        start_date = report.ipo_date if report.ipo_date else date.today() - timedelta(days=365)

        crawler = get_crawler()
        bars = crawler.get_stock_bars(
            ticker,
            start=start_date,
            end=date.today(),
        )

        if bars:
            fig = create_candlestick_chart(bars, report)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("暂无价格数据")
    except Exception as e:
        st.error(f"获取价格数据失败: {e}")

    # 四窗口状态
    st.subheader("🎯 四窗口状态")

    cols = st.columns(4)

    with cols[0]:
        st.markdown("**首日回调**")
        if report.windows.first_day_pullback.active:
            st.success("🟢 活跃")
            if report.windows.first_day_pullback.signal:
                st.write(f"信号: {report.windows.first_day_pullback.signal}")
        else:
            st.info("⚪ 未激活")

    with cols[1]:
        st.markdown("**底部突破**")
        if report.windows.ipo_base_breakout.base_detected:
            st.success("🟢 底部形成")
            if report.windows.ipo_base_breakout.breakout_signal:
                st.write(f"突破: {report.windows.ipo_base_breakout.breakout_signal}")
        else:
            st.info("⚪ 未形成")

    with cols[2]:
        st.markdown("**禁售期**")
        if report.windows.lockup_expiry.days_until is not None:
            days = report.windows.lockup_expiry.days_until
            if days <= 3:
                st.error(f"🔴 {days}天后到期")
            elif days <= 14:
                st.warning(f"🟡 {days}天后到期")
            else:
                st.info(f"⚪ {days}天后到期")
        else:
            st.info("⚪ 无数据")

    with cols[3]:
        st.markdown("**首次财报**")
        if report.windows.first_earnings.days_until is not None:
            days = report.windows.first_earnings.days_until
            st.info(f"⚪ {days}天后")
            if report.windows.first_earnings.earnings_signal:
                st.write(f"信号: {report.windows.first_earnings.earnings_signal}")
        else:
            st.info("⚪ 未安排")

    st.markdown("---")

    # 综合判断
    st.subheader("🧠 综合判断")

    signal_colors = {
        "STRONG_OPPORTUNITY": ("🎯", "#00ff88"),
        "OPPORTUNITY": ("📈", "#3b82f6"),
        "WATCH": ("👀", "#f59e0b"),
        "NO_ACTION": ("➖", "#64748b"),
    }

    emoji, color = signal_colors.get(report.overall_signal.value, ("❓", "#ffffff"))

    st.markdown(
        f"<h3 style='color: {color};'>{emoji} {report.overall_signal.value}</h3>",
        unsafe_allow_html=True,
    )

    if report.signal_reasons:
        st.write("**信号原因:**")
        for reason in report.signal_reasons:
            st.write(f"- {reason}")

    if report.risk_factors:
        st.error("**⚠️ 风险因素:**")
        for risk in report.risk_factors:
            st.write(f"- {risk}")


def create_candlestick_chart(bars: list[StockBar], report: CompositeReport) -> go.Figure:
    """创建K线图."""
    import pandas as pd

    df = pd.DataFrame([b.model_dump() for b in bars])
    df['date'] = pd.to_datetime(df['date'])

    fig = go.Figure()

    # K线
    fig.add_trace(go.Candlestick(
        x=df['date'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name=report.ticker,
    ))

    # IPO价格线
    if report.ipo_price:
        fig.add_hline(
            y=report.ipo_price,
            line_dash="dash",
            line_color="gray",
            annotation_text="IPO Price",
        )

    # 底部区域标注
    if (report.windows.ipo_base_breakout.base_detected and
        report.windows.ipo_base_breakout.base_details):
        base = report.windows.ipo_base_breakout.base_details
        if base.base_start and base.base_end:
            fig.add_vrect(
                x0=base.base_start,
                x1=base.base_end,
                fillcolor="blue",
                opacity=0.1,
                annotation_text="Base",
            )

    # 禁售期到期标注
    if report.windows.lockup_expiry.days_until is not None:
        expiry_date = date.today() + timedelta(days=report.windows.lockup_expiry.days_until)
        fig.add_vline(
            x=expiry_date,
            line_dash="dot",
            line_color="red",
            annotation_text="Lockup",
        )

    fig.update_layout(
        title=f"{report.ticker} 价格走势",
        yaxis_title="价格 ($)",
        xaxis_title="日期",
        template="plotly_dark",
        height=500,
        showlegend=False,
    )

    return fig


# IPO日历页
def render_calendar() -> None:
    """渲染IPO日历页面."""
    st.header("📅 IPO日历")

    tab1, tab2, tab3 = st.tabs(["即将上市", "即将到期禁售期", "即将发布财报"])

    with tab1:
        st.subheader("即将上市的IPO")

        try:
            crawler = get_crawler()
            upcoming = crawler.get_upcoming_ipos(days=30)

            if upcoming:
                df = pd.DataFrame([
                    {
                        "股票": e.ticker or "TBD",
                        "公司": e.company_name[:30] if e.company_name else "-",
                        "预计日期": e.expected_date,
                        "交易所": e.exchange or "-",
                        "价格区间": f"${e.price_range_low}-${e.price_range_high}"
                                   if e.price_range_low and e.price_range_high else "TBD",
                        "主承销商": e.lead_underwriter[:20] if e.lead_underwriter else "-",
                    }
                    for e in upcoming
                ])

                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("暂无即将上市的IPO数据")

        except Exception as e:
            st.error(f"获取数据失败: {e}")

    with tab2:
        st.subheader("即将到期的禁售期")

        try:
            lockup_tracker = get_aggregator().lockup
            expiries = lockup_tracker.get_upcoming_expiries(days_ahead=30)

            if expiries:
                df = pd.DataFrame([
                    {
                        "股票": e.ticker,
                        "到期日": e.lockup_expiry_date,
                        "剩余天数": (e.lockup_expiry_date - date.today()).days,
                        "供应冲击": f"{e.supply_impact_pct:.1%}" if e.supply_impact_pct else "-",
                    }
                    for e in expiries
                ])

                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("暂无禁售期到期数据")

        except Exception as e:
            st.error(f"获取数据失败: {e}")

    with tab3:
        st.subheader("即将发布的财报")

        try:
            radar = get_radar()
            tickers = radar.get_active_tickers()

            earnings_tracker = get_aggregator().earnings
            upcoming_earnings = earnings_tracker.get_upcoming_earnings(
                tickers, days_ahead=30
            )

            if upcoming_earnings:
                df = pd.DataFrame(upcoming_earnings)
                df['report_date'] = pd.to_datetime(df['report_date'])
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("暂无即将发布的财报")

        except Exception as e:
            st.error(f"获取数据失败: {e}")


# 观察名单管理
def render_watchlist_manager() -> None:
    """渲染观察名单管理页面."""
    st.header("📋 观察名单管理")

    radar = get_radar()

    # 添加股票
    st.subheader("添加股票")

    col1, col2 = st.columns([3, 1])

    with col1:
        new_ticker = st.text_input("股票代码", placeholder="如: CAVA").upper()

    with col2:
        ipo_date = st.date_input("IPO日期", value=None)

    if st.button("添加", type="primary"):
        if new_ticker:
            with st.spinner("添加中..."):
                if radar.add_to_watchlist(new_ticker, ipo_date):
                    st.success(f"✅ 已添加 {new_ticker}")
                else:
                    st.error(f"❌ 添加 {new_ticker} 失败")
        else:
            st.warning("请输入股票代码")

    st.markdown("---")

    # 当前观察名单
    st.subheader("当前观察名单")

    watchlist = radar.get_watchlist()

    if watchlist:
        df = pd.DataFrame([
            {
                "股票": s.ticker,
                "公司": s.company_name[:30] if s.company_name else "-",
                "上市日期": s.ipo_date,
                "状态": s.status,
                "当前价": f"${s.current_price:.2f}" if s.current_price else "-",
            }
            for s in watchlist
        ])

        st.dataframe(df, use_container_width=True, hide_index=True)

        # 删除功能
        st.markdown("---")
        st.subheader("移除股票")

        to_remove = st.selectbox(
            "选择要移除的股票",
            [s.ticker for s in watchlist],
        )

        if st.button("移除", type="secondary"):
            if radar.remove_from_watchlist(to_remove):
                st.success(f"✅ 已移除 {to_remove}")
                st.rerun()
            else:
                st.error("❌ 移除失败")
    else:
        st.info("观察名单为空")


# 主函数
def main() -> None:
    """主函数."""
    apply_custom_styles()

    # 渲染侧边栏并获取当前页面
    page = render_sidebar()

    # 根据页面渲染内容
    if page == "信号总览":
        render_overview()
    elif page == "个股详情":
        render_stock_detail()
    elif page == "IPO日历":
        render_calendar()
    elif page == "观察名单管理":
        render_watchlist_manager()


if __name__ == "__main__":
    main()
