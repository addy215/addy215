import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime
import time
from openai import OpenAI

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

# 内置 OpenAI API 配置
OPENAI_API_KEY = ""  # 替换为您的 API key
client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url="https://api.tu-zi.com/v1"
)

# Binance API 端点
BINANCE_API_URL = "https://api.binance.com/api/v3"

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
        response = requests.get(f"{BINANCE_API_URL}/exchangeInfo", timeout=10)
        response.raise_for_status()  # 检查 HTTP 状态码
        symbols = [s['symbol'] for s in response.json().get('symbols', [])]
        return f"{symbol}USDT" in symbols
    except requests.exceptions.Timeout:
        st.error("请求超时，请检查网络连接或稍后重试。")
    except requests.exceptions.RequestException as e:
        st.error(f"网络请求错误：{e}")
    except KeyError:
        st.error("API 返回数据格式错误，无法解析交易对信息。")
    return False

def get_klines_data(symbol, interval, limit=200):
    """获取K线数据"""
    try:
        params = {
            "symbol": f"{symbol}USDT",
            "interval": interval,
            "limit": limit
        }
        response = requests.get(f"{BINANCE_API_URL}/klines", params=params, timeout=10)
        response.raise_for_status()  # 检查 HTTP 状态码

        # 解析数据并转换为 DataFrame
        df = pd.DataFrame(response.json(), columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)

        return df
    except requests.exceptions.Timeout:
        st.error("请求超时，请检查网络连接或稍后重试。")
    except requests.exceptions.RequestException as e:
        st.error(f"网络请求错误：{e}")
    except ValueError:
        st.error("解析 K 线数据时发生错误，请检查 API 返回格式。")
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
        response = requests.get(f"{BINANCE_API_URL}/ticker/24hr", timeout=10)
        response.raise_for_status()
        data = response.json()
        usdt_pairs = [item for item in data if item['symbol'].endswith('USDT')]
        total_pairs = len(usdt_pairs)
        if total_pairs == 0:
            return "无法获取USDT交易对数据"

        up_pairs = [item for item in usdt_pairs if float(item['priceChangePercent']) > 0]
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
    except requests.exceptions.Timeout:
        return "请求超时，请稍后重试。"
    except requests.exceptions.RequestException as e:
        return f"获取市场情绪时发生错误: {e}"

def generate_trading_plan(symbol):
    """生成交易计划"""
    try:
        prompt = f"""
        请为交易对 {symbol}/USDT 提供一个详细的顺应趋势的交易计划。包括但不限于入场点、止损点、目标价位和资金管理策略。
        """
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"交易计划生成失败: {str(e)}"

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
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        tweet = response.choices[0].message.content.strip()
        if len(tweet) > 280:
            tweet = tweet[:277] + "..."
        return tweet
    except Exception as e:
        return f"推文生成失败: {str(e)}"

def get_ai_analysis(symbol, analysis_data, trading_plan):
    """获取 AI 分析结果"""
    try:
        prompt = f"""
        作为一位专业的加密货币分析师，请基于以下{symbol}的多周期分析数据提供详细的市场报告：

        各周期趋势分析：
        {analysis_data}

        详细交易计划：
        {trading_plan}

        请提供以下分析（使用markdown格式）：

        ## 市场综述
        [在多周期分析框架下的整体判断]

        ## 趋势分析
        - 短期趋势（5分钟-15分钟）：
        - 中期趋势（1小时-4小时）：
        - 长期趋势（日线）：
        - 趋势协同性分析：

        ## 关键价位
        - 主要阻力位：
        - 主要支撑位：
        - 当前价格位置分析：

        ## 未来目标预测
        1. 24小时目标：
        2. 3天目标：
        3. 7天目标：

        ## 操作建议
        - 短线操作：
        - 中线布局：
        - 风险提示：

        请确保分析专业、客观，并注意不同时间框架的趋势关系。
        """
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI 分析生成失败: {str(e)}"

# 主界面
col1, col2 = st.columns([2, 1])

with col1:
    symbol = st.text_input("输入代币代码（例如：BTC、ETH、PEPE）", value="BTC").upper()

with col2:
    analyze_button = st.button("开始分析", type="primary")

st.markdown("---")

if analyze_button:
    if check_symbol_exists(symbol):
        with st.spinner(f'正在分析 {symbol} 的市场状态...'):
            all_timeframe_analysis = {}

            for tf, info in TIMEFRAMES.items():
                df = get_klines_data(symbol, info['interval'])
                if df is not None:
                    df = calculate_indicators(df)
                    analysis = analyze_trend(df)
                    all_timeframe_analysis[info['name']] = analysis

            current_price = all_timeframe_analysis['日线']['current_price']
            st.metric(
                label=f"{symbol}/USDT 当前价格",
                value=f"${current_price:,.8f}" if current_price < 0.1 else f"${current_price:,.2f}"
            )

            trading_plan = generate_trading_plan(symbol)

            st.subheader("多周期分析报告")
            analysis = get_ai_analysis(symbol, all_timeframe_analysis, trading_plan)
            st.markdown(analysis)

            market_sentiment = get_market_sentiment()
            st.markdown("---")
            st.subheader("整体市场情绪")
            st.write(market_sentiment)

            st.markdown("---")
            st.subheader("多风格推文建议")

            analysis_summary = f"{analysis}\n市场情绪：{market_sentiment}"

            styles = {
                "女生风格": "女生",
                "交易员风格": "交易员",
                "分析师风格": "分析师",
                "媒体风格": "媒体"
            }

            col1, col2 = st.columns(2)

            for i, (style_name, style) in enumerate(styles.items()):
                tweet = generate_tweet(symbol, analysis_summary, style)
                if i < 2:
                    with col1:
                        st.subheader(f"📝 {style_name}")
                        st.text_area(
                            label="",
                            value=tweet,
                            height=150,
                            key=f"tweet_{style}"
                        )
                else:
                    with col2:
                        st.subheader(f"📝 {style_name}")
                        st.text_area(
                            label="",
                            value=tweet,
                            height=150,
                            key=f"tweet_{style}"
                        )

            st.caption(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        st.error(f"错误：{symbol}USDT 交易对在 Binance 上不存在，请检查代币代码是否正确。")

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

st.markdown("---")
st.caption("免责声明：本分析仅供参考，不构成投资建议。加密货币市场风险较大，请谨慎决策。")
