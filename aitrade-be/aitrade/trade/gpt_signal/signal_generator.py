import logging
from typing import Any, Dict

import httpx
import openai

from .market_analyzer import MarketAnalyzer
from .prompt_builder import PromptBuilder
from .response_parser import ResponseParser
from .technical_analyzer import TechnicalAnalyzer


class SignalGenerator:
    """串联技术分析、市场环境评估、提示词构建、模型调用与默认信号兜底。"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com/v1",
        proxy_url: str = None,
        model: str = "deepseek-chat",
    ):
        # 上层策略已经把 provider 差异收敛成最终 base_url，这里只负责创建 OpenAI 兼容客户端。
        logging.info('初始化 GPT 信号生成器: model=%s custom_base_url=%s proxy_enabled=%s', model, bool(base_url), bool(proxy_url))
        logging.debug("API基础URL: %s", base_url)
        logging.debug("模型名称: %s", model)

        if proxy_url:
            logging.info("使用代理: %s", proxy_url)
            http_client = httpx.Client(proxy=proxy_url, timeout=30.0)
        else:
            logging.info("不使用代理")
            http_client = httpx.Client(timeout=30.0)

        self.model = model
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=http_client,
        )
        logging.info("GPT信号生成器初始化完成")

    def _format_error_message(self, error: Exception) -> str:
        # 统一把底层 SDK、网络和代理错误收敛为更适合运维排查的中文信息。
        raw_message = str(error)
        normalized = raw_message.lower()

        if 'authentication fails' in normalized or 'authentication_error' in normalized or '401' in normalized:
            return 'AI 接口鉴权失败，请检查 app.gpt.api_key 是否正确'

        if 'using socks proxy' in normalized or 'socksio' in normalized:
            return '检测到 SOCKS 代理，但当前环境缺少 socksio 依赖；请安装 httpx[socks] 或改用 HTTP 代理'

        return raw_message

    def get_ai_signal(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        logging.info("开始获取AI交易信号")
        try:
            # 先在本地完成技术分析与市场环境摘要，尽量减少直接交给模型的原始数据噪音。
            logging.info("执行技术分析")
            tech_analysis = TechnicalAnalyzer.perform_technical_analysis(market_data)
            logging.debug(
                "技术分析完成，看涨信号: %s, 看跌信号: %s",
                tech_analysis.get('bullish_signals', 0),
                tech_analysis.get('bearish_signals', 0),
            )

            logging.info("评估市场环境")
            market_context = MarketAnalyzer.assess_market_context(market_data)
            logging.debug("市场环境评估完成: %s", market_context['details'])

            logging.info("构建AI分析提示词")
            prompt = PromptBuilder.build_analysis_prompt(market_data, tech_analysis, market_context)
            logging.debug("提示词构建完成")

            logging.info("调用AI模型进行分析")
            response = self._call_ai_model(prompt)
            logging.debug("AI模型调用完成")

            # 即便模型返回了文本，也必须先经过解析与结构校验，不能直接把自然语言结果交给执行层。
            logging.info("解析AI模型响应")
            signal = ResponseParser.parse_response(response)
            logging.debug("响应解析完成，建议操作: %s", signal.get('action', 'N/A'))

            logging.info("验证解析后的信号")
            if not ResponseParser.validate_signal(signal):
                logging.warning("信号验证失败，使用默认信号")
                signal = self._get_default_signal()
            else:
                logging.info("信号验证通过")

            logging.info("AI交易信号获取完成: %s (置信度: %.2f)", signal['action'], signal['confidence'])
            return signal
        except Exception as e:
            # AI 链路失败时返回默认信号而不是继续抛异常，避免单次模型故障直接中断整轮交易循环。
            logging.debug("AI 原始异常: %s", e)
            logging.error("获取AI交易信号时发生错误: %s", self._format_error_message(e))
            logging.info("使用默认信号")
            return self._get_default_signal()

    def _call_ai_model(self, prompt: str) -> str:
        logging.debug('开始调用AI模型: model=%s prompt_length=%s', self.model, len(prompt))
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": """你是一个专业的量化交易分析师。请基于提供的市场数据和技术指标进行综合分析，给出理性的交易建议。

分析原则：
1. 多重验证：至少需要2个以上技术指标支持同一方向
2. 风险优先：优先考虑风险管理，避免在不确定时交易
3. 趋势跟随：尊重当前趋势，不逆势操作
4. 概率思维：基于历史统计概率做出决策
""",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=500,
        )

        result = response.choices[0].message.content
        logging.debug('AI模型调用完成: response_length=%s', len(result or ''))
        return result

    def _get_default_signal(self) -> Dict[str, Any]:
        # 默认信号是降级保护，用来显式阻止在数据不足或 AI 调用失败时继续贸然交易。
        logging.info("生成默认信号")
        default_signal = {
            "action": "hold",
            "confidence": 0.3,
            "reason": "系统备用信号：数据不足或分析异常",
            "stop_loss_pct": 0.05,
            "take_profit_pct": 0.1,
            "expected_risk_reward": 2.0,
            "validity_period_hours": 1,
            "key_conditions": ["系统备用"],
        }
        logging.debug("默认信号生成完成: %s", default_signal)
        return default_signal
