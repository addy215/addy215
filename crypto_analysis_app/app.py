import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime
import time
import openai  # 导入 OpenAI 库

# 设置页面标题和说明
st.title("加密货币多周期分析系统")
st.markdown("""
### 使用说明
- 输入交易对代码（例如：BTC、ETH、PEPE等）
- 系统将自动分析多个时间周期的市场状态
- 提供专业的趋势分析和预测
- 分析整体市场情绪
- 提供详细的交易计划
- 生成多种风格的分析总结推文
""")

# 设置 OpenAI API 配置
OPENAI_API_KEY = ""  # 替换为您的 API key
openai.api_key = OPENAI_API_KEY

# Binance API 端点
BINANCE_API_URL = "https://api4.binance.com"

# 定义时间周期
TIMEFRAMES = {
    "5m": {"interval": "5m", "name": "5分钟"},
    "15m": {"interval": "15m", "name": "15分钟"},
    "1h": {"interval": "1h", "name": "1小时"},
    "4h": {"interval": "4h", "name": "4小时"},
    "1d": {"interval": "1d", "name": "日线"}
}

def check_symbol_exists(symbol):
    """检查交易对是否存在"""
    try:
        info_url = f"{BINANCE_API_URL}"
        response = requests.get(info_url)
        response.raise_for_status()
        symbols = [s['symbol'] for s in response.json()['symbols']]
        return f"{symbol}USDT" in symbols
    except Exception as e:
        st.error(f"检查交易对时发生错误: {str(e)}")
        return False

def get_klines_data(symbol, interval, limit=200):
    """获取K线数据"""
    try:
        klines_url = f"{BINANCE_API_URL}/klines"
        params = {
            "symbol": f"{symbol}USDT",
            "interval": interval,
            "limit": limit
        }
        response = requests.get(klines_url, params=params)
        response.raise_for_status()

        # 处理K线数据
        df = pd.DataFrame(response.json(), columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])

        # 转换数据类型
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
        info_url = f"{BINANCE_API_URL}/ticker/24hr"
        response = requests.get(info_url)
        response.raise_for_status()
        data = response.json()
        usdt_pairs = [item for item in data if item['symbol'].endswith('USDT')]
        total_pairs = len(usdt_pairs)
        if total_pairs == 0:
            return "无法获取USDT交易对数据"

        up_pairs = [item for item in usdt_pairs if float(item['priceChangePercent']) > 0]
        up_percentage = (len(up_pairs) / total_pairs) * 100

        # 分类情绪
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

def generate_tweet(symbol, analysis_summary, style):
    """生成推文内容"""
    try:
        style_prompts = {
            "女生": "以女生的语气",
            "交易员": "以交易员的专业语气",
            "分析师": "以金融分析师的专业语气",
            "媒体": "以媒体报道的客观语气"
        }

        style_prompt = style_prompts.get(style, "")

        prompt = f"""
        {style_prompt} 请根据以下分析总结，为交易对 {symbol}/USDT 撰写一条简洁且专业的推文，适合发布在推特上。推文应包括当前价格、市场情绪、主要趋势以及操作建议。限制在280个字符以内。

        分析总结：
        {analysis_summary}
        """
        
        # 调用 OpenAI API
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        
        # 提取推文内容
        tweet = response['choices'][0]['message']['content'].strip()
        
        # 确保推文不超过280字符
        if len(tweet) > 280:
            tweet = tweet[:277] + "..."
        
        return tweet
    except Exception as e:
        return f"推文生成失败: {str(e)}"

# 主界面
# 创建两列布局
col1, col2 = st.columns([2, 1])

with col1:
    # 用户输入代币代码
    symbol = st.text_input("输入代币代码（例如：BTC、ETH、PEPE）", value="BTC").upper()

with col2:
    # 分析按钮
    analyze_button = st.button("开始分析", type="primary")

# 添加分割线
st.markdown("---")

if analyze_button:
    # 检查代币是否存在
    if check_symbol_exists(symbol):
        with st.spinner(f'正在分析 {symbol} 的市场状态...'):
            all_timeframe_analysis = {}

            # 获取各个时间周期的数据并分析
            for tf, info in TIMEFRAMES.items():
                df = get_klines_data(symbol, info['interval'])
                if df is not None:
                    df = calculate_indicators(df)
                    analysis = analyze_trend(df)
                    all_timeframe_analysis[info['name']] = analysis

            # 显示当前价格
            current_price = all_timeframe_analysis['日线']['current_price']
            st.metric(
                label=f"{symbol}/USDT 当前价格",
                value=f"${current_price:,.8f}" if current_price < 0.1 else f"${current_price:,.2f}"
            )

            # 生成交易计划
            trading_plan = "请根据市场分析来制定适当的交易计划。"

            # 获取并显示 AI 分析
            st.subheader("多周期分析报告")
            analysis_summary = f"当前价格: {current_price}, 主要趋势: {all_timeframe_analysis['日线']['ma20_trend']}"
            st.write(analysis_summary)

            # 生成推文
            st.subheader("多风格推文建议")

            styles = ["女生", "交易员", "分析师", "媒体"]

            # 创建两列布局来显示推文
            col1, col2 = st.columns(2)

            # 生成并显示所有风格的推文
            for i, style in enumerate(styles):
                tweet = generate_tweet(symbol, analysis_summary, style)
                # 在左列显示前两个风格
                if i < 2:
                    with col1:
                        st.subheader(f"📝 {style} 风格")
                        st.text_area(
                            label="",
                            value=tweet,
                            height=150,
                            key=f"tweet_{style}"
                        )
                # 在右列显示后两个风格
                else:
                    with col2:
                        st.subheader(f"📝 {style} 风格")
                        st.text_area(
                            label="",
                            value=tweet,
                            height=150,
                            key=f"tweet_{style}"
                        )

            # 添加时间戳
            st.caption(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        st.error(f"错误：{symbol}USDT 交易对在 Binance 上不存在，请检查代币代码是否正确。")

# 自动刷新选项移到侧边栏
with st.sidebar:
    st.subheader("设置")
    auto_refresh = st.checkbox("启用自动刷新")
    if auto_refresh:
        refresh_interval = st.slider("刷新间隔（秒）", 30, 300, 60)
        st.caption(f"每 {refresh_interval} 秒自动刷新一次")
        time.sleep(refresh_interval)
        st.experimental_rerun()

    st.markdown("---")
    st.subheader("注意事项")
    st.write("请确保您的分析仅供参考，不构成投资建议。加密货币市场风险较大，请谨慎决策。")

# 添加页脚
st.markdown("---")
st.caption("免责声明：本分析仅供参考，不构成投资建议。加密货币市场风险较大，请谨慎决策。")
