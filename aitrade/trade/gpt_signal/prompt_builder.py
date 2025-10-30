import logging


class PromptBuilder:
    """AI提示词构建器
    
    负责构建发送给AI模型的提示词，将技术分析和市场环境数据
    格式化为AI模型易于理解的文本格式。
    """

    @staticmethod
    def build_analysis_prompt(market_data, technical_analysis, market_context):
        """构建分析提示词
        
        将市场数据、技术分析结果和市场环境评估整合成
        结构化的提示词，引导AI模型进行交易决策分析。
        
        Args:
            market_data (dict): 市场数据字典
            technical_analysis (dict): 技术分析结果
            market_context (dict): 市场环境评估结果
            
        Returns:
            str: 构建完成的提示词字符串
        """
        logging.info("开始构建AI分析提示词")
        
        # 构建完整的分析提示词
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

        logging.debug("AI分析提示词构建完成")
        return prompt