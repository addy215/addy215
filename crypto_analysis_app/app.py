import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime
import time
import os
from openai import OpenAI
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

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

# 获取 OpenAI API 密钥
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 初始化 OpenAI 客户端
client = OpenAI(api_key=OPENAI_API_KEY)

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
        info_url = f"{BINANCE_API_URL}/exchangeInfo"
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
        # 确保推文不超过280字符
        if len(tweet) > 280:
            tweet = tweet[:277] + "..."
        return tweet
    except Exception as e:
        return f"推文生成失败: {str(e)}"

def get_ai_analysis(symbol, analysis_data, trading_plan):
    """获取 AI 分析结果"""
    try:
        # 准备多周期分析数据
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
# 创建两列布局
col1, col2 = st.columns([2, 1])

with col1:
    symbol = st.text_input("请输入加密货币交易对 (例如：BTC、ETH等)：")
    if symbol:
        if check_symbol_exists(symbol):
            st.write(f"正在分析交易对：{symbol}USDT")

            # 获取历史K线数据
            df_5m = get_klines_data(symbol, TIMEFRAMES["5m"]["interval"])
            if df_5m is not None:
                df_5m = calculate_indicators(df_5m)
                trend_data = analyze_trend(df_5m)

                sentiment = get_market_sentiment()

                trading_plan = generate_trading_plan(symbol)

                # 推文生成
                style = st.selectbox("选择推文风格", ["女生", "交易员", "分析师", "媒体"])
                analysis_summary = f"当前价格: {trend_data['current_price']}，MA20趋势：{trend_data['ma20_trend']}，市场情绪：{sentiment}"
                tweet = generate_tweet(symbol, analysis_summary, style)

                ai_analysis = get_ai_analysis(symbol, analysis_summary, trading_plan)

                # 显示分析结果
                st.subheader(f"{symbol} 多周期分析结果")
                st.write(ai_analysis)

                st.subheader(f"推文生成：{style}")
                st.write(tweet)
                
        else:
            st.error(f"{symbol}USDT交易对不存在")

# 在右侧栏显示市场情绪和交易计划
with col2:
    st.subheader("市场情绪")
    st.write(sentiment)
    st.subheader("交易计划")
    st.write(trading_plan)

