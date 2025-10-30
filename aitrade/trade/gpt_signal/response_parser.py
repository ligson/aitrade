from typing import Dict, Any, Optional
import json
import re


class ResponseParser:
    """
    解析AI模型的响应并提取交易信号
    """

    @staticmethod
    def parse_response(response_text: str) -> Dict[str, Any]:
        """
        解析AI模型的响应文本
        
        Args:
            response_text: AI模型返回的原始文本
            
        Returns:
            包含解析后信号的字典
        """
        try:
            # 尝试提取JSON部分
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                signal = json.loads(json_str)
            else:
                # 如果没有找到JSON，使用默认值
                signal = {
                    "action": "hold",
                    "confidence": 0.5,
                    "reason": "从文本响应中解析",
                    "stop_loss_pct": 0.05,
                    "take_profit_pct": 0.1,
                    "expected_risk_reward": 2.0,
                    "validity_period_hours": 4,
                    "key_conditions": ["文本解析"]
                }

            return signal

        except Exception as e:
            # 出现异常时返回默认信号
            return {
                "action": "hold",
                "confidence": 0.5,
                "reason": "解析响应时出错",
                "stop_loss_pct": 0.05,
                "take_profit_pct": 0.1,
                "expected_risk_reward": 2.0,
                "validity_period_hours": 4,
                "key_conditions": ["默认解析"]
            }

    @staticmethod
    def validate_signal(parsed_result: Dict[str, Any]) -> bool:
        """
        验证解析后的信号是否有效
        
        Args:
            parsed_result: 解析后的信号结果
            
        Returns:
            如果信号有效返回True，否则返回False
        """
        action = parsed_result.get('action', '')
        confidence = parsed_result.get('confidence', 0)
        
        valid_action = action in ['buy', 'sell', 'hold']
        valid_confidence = 0 <= confidence <= 1
        
        return valid_action and valid_confidence