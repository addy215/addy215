import streamlit as st
import pandas as pd
import ccxt
from datetime import datetime

# 设置页面标题和说明
st.title("加密货币多周期分析系统")
st.markdown("""
### 使用说明
- 输入交易对代码（例如：BTC、ETH、PEPE等）
- 系统将自动分析多个时间周期的市场状态
- 提供专业的趋势分析和预测
- 分析整体市场情绪
""")

# 初始化 ccxt 的 OKEx 实例
okex = ccxt.okex({"rateLimit": 1200, "enableRateLimit": True})

# 定义时间周期
TIMEFRAMES = {
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d"
}

def check_symbol_exists(symbol):
    """检查交易对是否存在"""
    try:
        markets = okex.load_markets()
        return f"{symbol}/USDT" in markets
    except Exception as e:
        st.error(f"检查交易对时发生错误: {e}")
        return False

def get_klines_data(symbol, timeframe, limit=200):
    """获取K线数据"""
    try:
        ohlcv = okex.fetch_ohlcv(f"{symbol}/USDT", timeframe=timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        return df
    except Exception as e:
        st.error(f"获取K线数据时发生错误: {str(e)}")
        return None

def calculate_indicators(df):
    """计算技术指标"""
    # 计算MA20
    df['ma20'] = df['close'].rolling(window=20).mean()

    # 计算BOLL指标
    df['boll_mid'] = df['close'].rolling(window=20).mean()
    df['boll_std'] = df['close'].rolling(window=20).std()
    df['boll_up'] = df['boll_mid'] + 2 * df['boll_std']
    df['boll_down'] = df['boll_mid'] - 2 * df['boll_std']

    # 计算MA20趋势
    df['ma20_trend'] = df['ma20'].diff().rolling(window=5).mean()

    return df

def analyze_trend(df):
    """分析趋势"""
    current_price = df['close'].iloc[-1]
    ma20_trend = "上升" if df['ma20_trend'].iloc[-1] > 0 else "下降"

    # BOLL带支撑阻力
    boll_up = df['boll_up'].iloc[-1]
    boll_mid = df['boll_mid'].iloc[-1]
    boll_down = df['boll_down'].iloc[-1]

    return {
        "current_price": current_price,
        "ma20_trend": ma20_trend,
        "support_resistance": {
            "strong_resistance": boll_up,
            "middle_line": boll_mid,
            "strong_support": boll_down
        }
    }

def get_market_sentiment():
    """获取市场情绪"""
    try:
        tickers = okex.fetch_tickers()
        usdt_pairs = [symbol for symbol in tickers if symbol.endswith('/USDT')]
        total_pairs = len(usdt_pairs)
        if total_pairs == 0:
            return "无法获取USDT交易对数据"

        up_pairs = [symbol for symbol in usdt_pairs if tickers[symbol]['percentage'] > 0]
        up_percentage = (len(up_pairs) / total_pairs) * 100

        if up_percentage >= 80:
            sentiment = "极端乐观"
        elif up_percentage >= 60:
            sentiment = "乐观"
        elif up_percentage >= 40:
            sentiment = "中性"
        elif up_percentage >= 20:
            sentiment = "悲观"
        else:
            sentiment = "极端悲观"

        return f"市场情绪：{sentiment}（上涨交易对占比 {up_percentage:.2f}%）"
    except Exception as e:
        return f"获取市场情绪时发生错误: {str(e)}"

# 主界面
col1, col2 = st.columns([2, 1])

with col1:
    # 用户输入代币代码
    symbol = st.text_input("输入代币代码（例如：BTC、ETH、PEPE）", value="BTC").upper()

with col2:
    # 分析按钮
    analyze_button = st.button("开始分析", type="primary")

st.markdown("---")

if analyze_button:
    if check_symbol_exists(symbol):
        with st.spinner(f'正在分析 {symbol} 的市场状态...'):
            all_timeframe_analysis = {}

            for tf, tf_name in TIMEFRAMES.items():
                df = get_klines_data(symbol, tf_name)
                if df is not None:
                    df = calculate_indicators(df)
                    analysis = analyze_trend(df)
                    all_timeframe_analysis[tf_name] = analysis

            current_price = all_timeframe_analysis['1d']['current_price']
            st.metric(
                label=f"{symbol}/USDT 当前价格",
                value=f"${current_price:,.8f}" if current_price < 0.1 else f"${current_price:,.2f}"
            )

            market_sentiment = get_market_sentiment()
            st.markdown("---")
            st.subheader("整体市场情绪")
            st.write(market_sentiment)

            st.markdown("---")
            st.subheader("多周期分析报告")
            for tf_name, analysis in all_timeframe_analysis.items():
                st.write(f"### {tf_name} 分析")
                st.json(analysis)

            st.caption(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        st.error(f"错误：{symbol}/USDT 交易对在 OKEx 上不存在，请检查代币代码是否正确。")
