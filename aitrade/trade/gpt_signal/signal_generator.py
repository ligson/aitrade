import logging
import openai
import httpx
from typing import Dict, Any, Optional
from .technical_analyzer import TechnicalAnalyzer
from .market_analyzer import MarketAnalyzer
from .prompt_builder import PromptBuilder
from .response_parser import ResponseParser


class SignalGenerator:
    """
    GPT交易信号生成器主类
    
    协调各个组件完成完整的交易信号生成流程：
    1. 技术分析
    2. 市场环境分析
    3. 构建提示词
    4. 调用AI模型
    5. 解析响应
    6. 验证信号
    """

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com/v1", proxy_url: str = None):
        """
        初始化信号生成器
        
        Args:
            api_key (str): DeepSeek API密钥
            base_url (str): API基础URL
            proxy_url (str): 代理URL（如果需要）
        """
        logging.info("初始化GPT信号生成器")
        logging.debug(f"API基础URL: {base_url}")
        
        # 配置HTTP客户端
        if proxy_url:
            logging.info(f"使用代理: {proxy_url}")
            http_client = httpx.Client(proxy=proxy_url, timeout=30.0)
        else:
            logging.info("不使用代理")
            http_client = httpx.Client(timeout=30.0)
            
        # 初始化OpenAI客户端
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=http_client
        )
        logging.info("GPT信号生成器初始化完成")

    def get_ai_signal(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取AI交易信号
        
        执行完整的信号生成流程，包括技术分析、市场分析、
        AI调用和结果解析验证。
        
        Args:
            market_data (Dict[str, Any]): 包含价格、成交量等数据的字典
            
        Returns:
            Dict[str, Any]: 包含交易信号和其他信息的字典
        """
        logging.info("开始获取AI交易信号")
        try:
            # 1. 技术分析
            logging.info("执行技术分析")
            tech_analysis = TechnicalAnalyzer.perform_technical_analysis(market_data)
            logging.debug(f"技术分析完成，看涨信号: {tech_analysis.get('bullish_signals', 0)}, 看跌信号: {tech_analysis.get('bearish_signals', 0)}")
            
            # 2. 市场环境分析
            logging.info("评估市场环境")
            market_context = MarketAnalyzer.assess_market_context(market_data)
            logging.debug(f"市场环境评估完成: {market_context['details']}")
            
            # 3. 构建提示词
            logging.info("构建AI分析提示词")
            prompt = PromptBuilder.build_analysis_prompt(market_data, tech_analysis, market_context)
            logging.debug("提示词构建完成")
            
            # 4. 调用AI模型
            logging.info("调用AI模型进行分析")
            response = self._call_ai_model(prompt)
            logging.debug("AI模型调用完成")
            
            # 5. 解析响应
            logging.info("解析AI模型响应")
            signal = ResponseParser.parse_response(response)
            logging.debug(f"响应解析完成，建议操作: {signal.get('action', 'N/A')}")
            
            # 6. 验证信号
            logging.info("验证解析后的信号")
            if not ResponseParser.validate_signal(signal):
                logging.warning("信号验证失败，使用默认信号")
                signal = self._get_default_signal()
            else:
                logging.info("信号验证通过")
                
            logging.info(f"AI交易信号获取完成: {signal['action']} (置信度: {signal['confidence']})")
            return signal
            
        except Exception as e:
            # 出现异常时返回默认信号
            logging.error(f"获取AI交易信号时发生错误: {e}")
            logging.info("使用默认信号")
            return self._get_default_signal()

    def _call_ai_model(self, prompt: str) -> str:
        """
        调用AI模型获取响应
        
        Args:
            prompt (str): 发送给AI模型的提示词
            
        Returns:
            str: AI模型的响应文本
        """
        logging.debug("开始调用AI模型")
        response = self.client.chat.completions.create(
            model="deepseek-chat",
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
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=500
        )
        
        result = response.choices[0].message.content
        logging.debug("AI模型调用完成")
        return result

    def _get_default_signal(self) -> Dict[str, Any]:
        """
        获取默认信号（出现错误时使用）
        
        Returns:
            Dict[str, Any]: 默认的持有信号
        """
        logging.info("生成默认信号")
        default_signal = {
            "action": "hold",
            "confidence": 0.3,
            "reason": "系统备用信号：数据不足或分析异常",
            "stop_loss_pct": 0.05,
            "take_profit_pct": 0.1,
            "expected_risk_reward": 2.0,
            "validity_period_hours": 1,
            "key_conditions": ["系统备用"]
        }
        logging.debug(f"默认信号生成完成: {default_signal}")
        return default_signal