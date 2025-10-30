import logging
from typing import Dict, Any, Optional
import json
import re


class ResponseParser:
    """
    解析AI模型的响应并提取交易信号
    
    负责将AI模型返回的文本响应解析为结构化的交易信号，
    包括操作建议、置信度、风险参数等关键信息。
    """

    @staticmethod
    def parse_response(response_text: str) -> Dict[str, Any]:
        """
        解析AI模型的响应文本
        
        尝试从AI模型的响应中提取JSON格式的交易信号，
        如果提取失败则返回默认信号。
        
        Args:
            response_text (str): AI模型返回的原始文本
            
        Returns:
            Dict[str, Any]: 包含解析后信号的字典
        """
        logging.info("开始解析AI模型响应")
        try:
            # 尝试提取JSON部分
            logging.debug("尝试从响应中提取JSON数据")
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                logging.debug("找到JSON格式数据，尝试解析")
                signal = json.loads(json_str)
                logging.info("AI响应解析成功")
            else:
                # 如果没有找到JSON，使用默认值
                logging.warning("未找到JSON格式数据，使用默认信号")
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

        except json.JSONDecodeError as e:
            # JSON解析错误时返回默认信号
            logging.error(f"JSON解析失败: {e}")
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
        except Exception as e:
            # 出现其他异常时返回默认信号
            logging.error(f"解析响应时出现未知错误: {e}")
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
        
        检查解析后的信号是否包含必要的字段且值在合理范围内。
        
        Args:
            parsed_result (Dict[str, Any]): 解析后的信号结果
            
        Returns:
            bool: 如果信号有效返回True，否则返回False
        """
        logging.info("开始验证解析后的信号")
        action = parsed_result.get('action', '')
        confidence = parsed_result.get('confidence', 0)
        
        # 验证操作建议是否有效
        valid_action = action in ['buy', 'sell', 'hold']
        if not valid_action:
            logging.warning(f"无效的操作建议: {action}")
        
        # 验证置信度是否在有效范围内
        valid_confidence = 0 <= confidence <= 1
        if not valid_confidence:
            logging.warning(f"置信度超出有效范围: {confidence}")
        
        is_valid = valid_action and valid_confidence
        if is_valid:
            logging.info("信号验证通过")
        else:
            logging.warning("信号验证失败")
            
        return is_valid