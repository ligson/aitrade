import logging

from ..gpt_signal import SignalGenerator
from .base_strategy import BaseStrategy


class GPTStrategy(BaseStrategy):
    name = 'gpt'

    def __init__(self, runtime_config):
        super().__init__(runtime_config.trade_strategy_gpt_config)
        self.min_confidence = self.config.get('min_confidence', 0.7)
        self.signal_generator = SignalGenerator(
            api_key=runtime_config.gpt_api_key,
            base_url=self._resolve_base_url(runtime_config.gpt_provider),
            proxy_url=runtime_config.proxy_url if runtime_config.proxy_enable else None,
            model=runtime_config.gpt_model,
        )

    def get_required_history(self) -> int:
        return 35

    def generate_signal(self, market_data, position):
        signal = self.signal_generator.get_ai_signal(market_data)
        signal['strategy'] = self.name
        signal.setdefault('stop_loss_pct', 0.05)
        signal.setdefault('risk_per_trade', 0.02)

        if signal['action'] != 'hold' and signal.get('confidence', 0) < self.min_confidence:
            logging.info(
                "GPT信号置信度 %.2f 低于阈值 %.2f，转为观望",
                signal.get('confidence', 0),
                self.min_confidence,
            )
            return {
                'action': 'hold',
                'confidence': signal.get('confidence', 0),
                'reason': f"GPT信号置信度低于阈值 {self.min_confidence:.2f}",
                'strategy': self.name,
                'stop_loss_pct': signal.get('stop_loss_pct', 0.05),
                'risk_per_trade': signal.get('risk_per_trade', 0.02),
                'meta': {
                    'original_action': signal.get('action'),
                    'original_reason': signal.get('reason'),
                },
            }

        return signal

    @staticmethod
    def _resolve_base_url(provider: str) -> str:
        if provider == 'openai':
            logging.info("使用OpenAI API作为AI服务提供商")
            return 'https://api.openai.com/v1'

        if provider != 'deepseek':
            logging.warning("未知的AI服务提供商: %s，默认使用DeepSeek", provider)

        logging.info("使用DeepSeek API作为AI服务提供商")
        return 'https://api.deepseek.com/v1'
