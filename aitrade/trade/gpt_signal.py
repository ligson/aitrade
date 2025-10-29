import json

from ..config import config
import httpx
import numpy as np
from openai import OpenAI


def init_gpt_client(cfg: config.Config) -> OpenAI:
    global client
    if cfg.proxy_enable:
        http_client = httpx.Client(
            proxy=cfg.proxy_url,
            timeout=30.0  # 增加超时时间到30秒
        )
    else:
        http_client = httpx.Client(
            timeout=30.0  # 增加超时时间到30秒
        )

    if cfg.gpt_provider == 'deepseek':
        client = OpenAI(
            base_url="https://api.deepseek.com",
            http_client=http_client
        )
    if cfg.gpt_provider == 'openai':
        client = OpenAI(
            http_client=http_client
        )
    return client


def get_ai_signal(cfg: config.Config, market_data):
    gpt_client = init_gpt_client(cfg)
    """完善的AI信号生成函数"""
    try:
        # 提取技术指标数据
        technicals = market_data.get('technicals', {})
        closes = market_data.get('closes', [])
        volumes = market_data.get('volumes', [])
        current_price = market_data.get('price', 0)

        # 技术指标状态分析
        rsi = technicals.get('rsi', 50)
        macd_line = technicals.get('macd_line', 0)
        macd_signal = technicals.get('macd_signal', 0)
        macd_histogram = technicals.get('macd_histogram', 0)

        # 计算技术信号强度
        technical_analysis = analyze_technical_conditions(
            rsi, macd_line, macd_signal, macd_histogram, closes, volumes
        )

        # 市场状态评估
        market_context = assess_market_context(closes, volumes, current_price)

        # 构建详细的提示词
        prompt = build_analysis_prompt(market_data, technical_analysis, market_context)

        # 调用AI模型
        response = gpt_client.chat.completions.create(model="deepseek-chat",
                                                      messages=[
                                                          {
                                                              "role": "system",
                                                              "content": """你是一个专业的量化交易分析师。请基于提供的市场数据和技术指标进行综合分析，给出理性的交易建议。
                        
                        分析原则：
                        1. 多重验证：至少需要2个以上技术指标支持同一方向
                        2. 风险优先：优先考虑风险管理，避免在不确定时交易
                        3. 趋势跟随：尊重当前趋势，不逆势操作
                        4. 概率思维：基于历史统计概率做出决策
                        """
                                                          },
                                                          {
                                                              "role": "user",
                                                              "content": prompt
                                                          }
                                                      ],
                                                      temperature=0.1,  # 低随机性保证一致性
                                                      max_tokens=500)

        # 解析AI响应
        ai_response = response.choices[0].message.content.strip()
        signal = parse_ai_response(ai_response)

        # 验证信号合理性
        validated_signal = validate_signal(signal, technical_analysis, market_context)

        return validated_signal

    except Exception as e:
        print(f"AI信号生成错误: {e}")
        return get_fallback_signal(market_data)


def analyze_technical_conditions(rsi, macd_line, macd_signal, macd_histogram, closes, volumes):
    """分析技术条件并计算信号强度"""

    # RSI分析
    rsi_analysis = {
        'value': rsi,
        'condition': 'neutral',
        'strength': 0,
        'details': ''
    }

    if rsi < 30:
        rsi_analysis.update({'condition': 'oversold', 'strength': min(1.0, (30 - rsi) / 30)})
        rsi_analysis['details'] = f'RSI {rsi:.1f} 处于超卖区域'
    elif rsi > 70:
        rsi_analysis.update({'condition': 'overbought', 'strength': min(1.0, (rsi - 70) / 30)})
        rsi_analysis['details'] = f'RSI {rsi:.1f} 处于超买区域'
    else:
        rsi_analysis['strength'] = 0.5
        rsi_analysis['details'] = f'RSI {rsi:.1f} 处于中性区域'

    # MACD分析
    macd_analysis = {
        'trend': 'neutral',
        'momentum': 0,
        'crossover': 'none',
        'details': ''
    }

    # MACD趋势判断
    if macd_histogram > 0:
        macd_analysis['trend'] = 'bullish'
        macd_analysis['momentum'] = min(1.0, float(macd_histogram) / (abs(float(macd_line)) + 1e-10))
    else:
        macd_analysis['trend'] = 'bearish'
        macd_analysis['momentum'] = min(1.0, abs(float(macd_histogram)) / (abs(float(macd_line)) + 1e-10))

    # 金叉死叉判断
    if macd_line > macd_signal and macd_histogram > 0:
        macd_analysis['crossover'] = 'golden'
        macd_analysis['details'] = 'MACD金叉，看涨信号'
    elif macd_line < macd_signal and macd_histogram < 0:
        macd_analysis['crossover'] = 'death'
        macd_analysis['details'] = 'MACD死叉，看跌信号'
    else:
        macd_analysis['details'] = 'MACD无明显交叉信号'

    # 价格趋势分析
    price_trend = analyze_price_trend(closes)

    # 成交量分析
    volume_analysis = analyze_volume(volumes)

    # 综合信号强度
    bullish_signals = 0
    bearish_signals = 0

    if rsi_analysis['condition'] == 'oversold':
        bullish_signals += 1
    elif rsi_analysis['condition'] == 'overbought':
        bearish_signals += 1

    if macd_analysis['crossover'] == 'golden':
        bullish_signals += 1
    elif macd_analysis['crossover'] == 'death':
        bearish_signals += 1

    if price_trend['trend'] == 'up':
        bullish_signals += 1
    elif price_trend['trend'] == 'down':
        bearish_signals += 1

    if volume_analysis['trend'] == 'increasing':
        bullish_signals += 1

    total_signals = max(bullish_signals + bearish_signals, 1)
    overall_strength = abs(bullish_signals - bearish_signals) / total_signals

    return {
        'rsi': rsi_analysis,
        'macd': macd_analysis,
        'price_trend': price_trend,
        'volume': volume_analysis,
        'bullish_signals': bullish_signals,
        'bearish_signals': bearish_signals,
        'overall_strength': overall_strength,
        'signal_bias': 'bullish' if bullish_signals > bearish_signals else 'bearish' if bearish_signals > bullish_signals else 'neutral'
    }


def analyze_price_trend(closes, short_period=10, long_period=20):
    """分析价格趋势"""
    if len(closes) < long_period:
        return {'trend': 'neutral', 'strength': 0, 'details': '数据不足'}

    short_ma = sum(closes[-short_period:]) / short_period
    long_ma = sum(closes[-long_period:]) / long_period
    current_price = closes[-1]

    # 趋势判断
    if current_price > short_ma > long_ma:
        trend = 'up'
        strength = min(1.0, (current_price - long_ma) / long_ma * 10)
    elif current_price < short_ma < long_ma:
        trend = 'down'
        strength = min(1.0, (long_ma - current_price) / long_ma * 10)
    else:
        trend = 'neutral'
        strength = 0.5

    return {
        'trend': trend,
        'strength': strength,
        'details': f'价格趋势: {trend}, 短期MA: {short_ma:.2f}, 长期MA: {long_ma:.2f}'
    }


def analyze_volume(volumes, period=10):
    """分析成交量"""
    if len(volumes) < period:
        return {'trend': 'neutral', 'details': '数据不足'}

    recent_volume = sum(volumes[-5:]) / 5
    historical_volume = sum(volumes[-period:]) / period

    if recent_volume > historical_volume * 1.2:
        trend = 'increasing'
        details = f'成交量放大 {recent_volume / historical_volume:.1f}倍'
    elif recent_volume < historical_volume * 0.8:
        trend = 'decreasing'
        details = f'成交量萎缩至平均的 {recent_volume / historical_volume:.1f}倍'
    else:
        trend = 'stable'
        details = '成交量稳定'

    return {'trend': trend, 'details': details}


def assess_market_context(closes, volumes, current_price):
    """评估市场整体环境"""
    if len(closes) < 20:
        return {'volatility': 'unknown', 'trend': 'unknown', 'details': '数据不足'}

    # 波动率分析
    returns = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
    volatility = np.std(returns) * np.sqrt(365)  # 年化波动率

    volatility_level = 'high' if volatility > 0.8 else 'medium' if volatility > 0.4 else 'low'

    # 趋势强度
    price_change = (current_price - closes[0]) / closes[0]
    trend_strength = 'strong' if abs(price_change) > 0.1 else 'moderate' if abs(price_change) > 0.05 else 'weak'
    trend_direction = 'up' if price_change > 0 else 'down' if price_change < 0 else 'flat'

    return {
        'volatility': volatility_level,
        'trend_strength': trend_strength,
        'trend_direction': trend_direction,
        'price_change_pct': price_change * 100,
        'details': f'市场{trend_direction}趋势{trend_strength}, 波动率{volatility_level}'
    }


def build_analysis_prompt(market_data, technical_analysis, market_context):
    """构建分析提示词"""

    prompt = f"""
    请基于以下市场数据提供专业的交易分析：

    【市场概况】
    - 当前价格: {market_data.get('price', 'N/A')}
    - 时间: {market_data.get('timestamp', 'N/A')}
    - 市场状态: {market_context['details']}

    【技术指标详情】
    RSI指标:
    - 数值: {technical_analysis['rsi']['value']:.1f}
    - 状态: {technical_analysis['rsi']['condition']}
    - 强度: {technical_analysis['rsi']['strength']:.2f}
    - 说明: {technical_analysis['rsi']['details']}

    MACD指标:
    - 趋势: {technical_analysis['macd']['trend']}
    - 动量: {technical_analysis['macd']['momentum']:.2f}
    - 交叉信号: {technical_analysis['macd']['crossover']}
    - 说明: {technical_analysis['macd']['details']}

    价格趋势:
    - 方向: {technical_analysis['price_trend']['trend']}
    - 强度: {technical_analysis['price_trend']['strength']:.2f}
    - 说明: {technical_analysis['price_trend']['details']}

    成交量:
    - 趋势: {technical_analysis['volume']['trend']}
    - 说明: {technical_analysis['volume']['details']}

    【信号汇总】
    - 看涨信号数量: {technical_analysis['bullish_signals']}
    - 看跌信号数量: {technical_analysis['bearish_signals']}
    - 总体偏向: {technical_analysis['signal_bias']}
    - 信号强度: {technical_analysis['overall_strength']:.2f}

    【分析要求】
    请基于以上数据：
    1. 评估当前市场多空力量对比
    2. 识别主要的技术信号和矛盾点
    3. 给出具体的交易建议和置信度
    4. 设置合理的风险参数

    请以JSON格式输出分析结果：
    {{
        "action": "buy/sell/hold",
        "confidence": 0.0-1.0,
        "reason": "详细的分析理由，包括支持信号和风险因素",
        "stop_loss_pct": 0.02-0.08,
        "take_profit_pct": 0.04-0.15,
        "expected_risk_reward": 1.5-3.0,
        "validity_period_hours": 1-24,
        "key_conditions": ["主要依赖的条件1", "条件2"]
    }}
    """

    return prompt


def parse_ai_response(ai_response):
    """解析AI响应"""
    try:
        # 尝试提取JSON部分
        json_start = ai_response.find('{')
        json_end = ai_response.rfind('}') + 1

        if json_start >= 0 and json_end > json_start:
            json_str = ai_response[json_start:json_end]
            signal = json.loads(json_str)
        else:
            # 如果没有找到JSON，使用正则表达式提取
            import re
            action_match = re.search(r'"action":\s*"(\w+)"', ai_response)
            confidence_match = re.search(r'"confidence":\s*([0-9.]+)', ai_response)

            signal = {
                "action": action_match.group(1) if action_match else "hold",
                "confidence": float(confidence_match.group(1)) if confidence_match else 0.5,
                "reason": "从文本响应中解析",
                "stop_loss_pct": 0.05,
                "take_profit_pct": 0.1,
                "expected_risk_reward": 2.0,
                "validity_period_hours": 4,
                "key_conditions": ["文本解析"]
            }

        return signal

    except Exception as e:
        print(f"解析AI响应错误: {e}")
        return get_fallback_signal()


def validate_signal(signal, technical_analysis, market_context):
    """验证信号合理性"""

    # 基本验证
    if signal['action'] not in ['buy', 'sell', 'hold']:
        signal['action'] = 'hold'

    if not (0 <= signal['confidence'] <= 1):
        signal['confidence'] = max(0, min(1, signal['confidence']))

    # 基于技术分析的验证
    if signal['action'] == 'buy':
        # 买入信号需要更多验证
        if (technical_analysis['rsi']['condition'] == 'overbought' and
                technical_analysis['rsi']['strength'] > 0.7):
            signal['action'] = 'hold'
            signal['confidence'] *= 0.5
            signal['reason'] += " | 调整: RSI严重超买，避免买入"

    elif signal['action'] == 'sell':
        # 卖出信号验证
        if (technical_analysis['rsi']['condition'] == 'oversold' and
                technical_analysis['rsi']['strength'] > 0.7):
            signal['action'] = 'hold'
            signal['confidence'] *= 0.5
            signal['reason'] += " | 调整: RSI严重超卖，避免卖出"

    # 高波动市场降低置信度
    if market_context['volatility'] == 'high':
        signal['confidence'] *= 0.7
        signal['stop_loss_pct'] = min(signal.get('stop_loss_pct', 0.05) * 1.5, 0.1)

    return signal


def get_fallback_signal(market_data=None):
    """备用信号生成"""
    return {
        "action": "hold",
        "confidence": 0.3,
        "reason": "系统备用信号：数据不足或分析异常",
        "stop_loss_pct": 0.05,
        "take_profit_pct": 0.1,
        "expected_risk_reward": 2.0,
        "validity_period_hours": 1,
        "key_conditions": ["系统备用"]
    }
