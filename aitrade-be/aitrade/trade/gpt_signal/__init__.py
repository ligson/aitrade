"""
GPT信号生成模块

该模块负责生成基于AI分析的交易信号，主要包含以下组件：
- SignalGenerator: 主信号生成器，协调其他组件工作
- TechnicalAnalyzer: 技术指标分析器，计算和分析各种技术指标
- MarketAnalyzer: 市场环境分析器，评估整体市场环境
- PromptBuilder: AI提示词构建器，构建发送给AI模型的提示词
- ResponseParser: AI响应解析器，解析AI模型的响应
- ResponseParser: AI响应解析器，解析AI模型的响应

整个流程如下：
1. TechnicalAnalyzer 分析技术指标
2. MarketAnalyzer 评估市场环境
3. PromptBuilder 构建分析提示词
4. SignalGenerator 调用AI模型
5. ResponseParser 解析AI响应并生成交易信号
"""

from .signal_generator import SignalGenerator

__all__ = ['SignalGenerator']