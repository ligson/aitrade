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
    """

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com/v1", proxy_url: str = None):
        """
        初始化信号生成器
        
        Args:
            api_key: DeepSeek API密钥
            base_url: API基础URL
            proxy_url: 代理URL（如果需要）
        """
        if proxy_url:
            http_client = httpx.Client(proxy=proxy_url, timeout=30.0)
        else:
            http_client = httpx.Client(timeout=30.0)
            
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=http_client
        )

    def get_ai_signal(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取AI交易信号
        
        Args:
            market_data: 包含价格、成交量等数据的字典
            
        Returns:
            包含交易信号和其他信息的字典
        """
        try:
            # 1. 技术分析
            tech_analysis = TechnicalAnalyzer.perform_technical_analysis(market_data)
            
            # 2. 市场环境分析
            market_context = MarketAnalyzer.assess_market_context(market_data)
            
            # 3. 构建提示词
            prompt = PromptBuilder.build_analysis_prompt(market_data, tech_analysis, market_context)
            
            # 4. 调用AI模型
            response = self._call_ai_model(prompt)
            
            # 5. 解析响应
            signal = ResponseParser.parse_response(response)
            
            # 6. 验证信号
            if not ResponseParser.validate_signal(signal):
                signal = self._get_default_signal()
                
            return signal
            
        except Exception as e:
            # 出现异常时返回默认信号
            return self._get_default_signal()

    def _call_ai_model(self, prompt: str) -> str:
        """
        调用AI模型获取响应
        
        Args:
            prompt: 发送给AI模型的提示词
            
        Returns:
            AI模型的响应文本
        """
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
        
        return response.choices[0].message.content

    def _get_default_signal(self) -> Dict[str, Any]:
        """
        获取默认信号（出现错误时使用）
        
        Returns:
            默认的持有信号
        """
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