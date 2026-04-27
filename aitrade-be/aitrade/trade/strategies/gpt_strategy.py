import logging

from ..gpt_signal import SignalGenerator
from .base_strategy import BaseStrategy


class GPTStrategy(BaseStrategy):
    name = 'gpt'

    def __init__(self, runtime_config):
        super().__init__(runtime_config.trade_strategy_gpt_config)
        self.min_confidence = self.config.get('min_confidence', 0.7)
        # Web 场景下传入的 runtime_config 已经是“文件配置 + 系统设置覆盖”后的生效配置；
        # 只有当页面未显式填写 base_url 时，才按 provider 推导默认端点。
        resolved_base_url = runtime_config.gpt_base_url or self._resolve_base_url(runtime_config.gpt_provider)
        logging.info(
            '初始化 GPT 策略: provider=%s model=%s custom_base_url=%s min_confidence=%.2f',
            runtime_config.gpt_provider,
            runtime_config.gpt_model,
            bool(runtime_config.gpt_base_url),
            self.min_confidence,
        )
        self.signal_generator = SignalGenerator(
            api_key=runtime_config.gpt_api_key,
            base_url=resolved_base_url,
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

        # 最小置信度阈值由 GPT 策略自身负责，而不是交给上层调度器统一硬编码；
        # 这样策略层可以在保留原始判断理由的同时，把低置信度交易意图降级为 hold。
        if signal['action'] != 'hold' and signal.get('confidence', 0) < self.min_confidence:
            logging.debug(
                'GPT 原始信号低于阈值: action=%s confidence=%.2f threshold=%.2f',
                signal.get('action'),
                signal.get('confidence', 0),
                self.min_confidence,
            )
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
        # 这里只负责 provider 到默认端点的兜底映射；
        # 如果页面已经显式保存了自定义 base_url，则不会走到这里。
        if provider == 'openai':
            logging.info("使用OpenAI API作为AI服务提供商")
            return 'https://api.openai.com/v1'

        if provider != 'deepseek':
            logging.warning("未知的AI服务提供商: %s，默认使用DeepSeek", provider)

        logging.info("使用DeepSeek API作为AI服务提供商")
        return 'https://api.deepseek.com/v1'
