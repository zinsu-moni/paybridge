import logging
from typing import Any, Dict, Optional
from venv import logger
from .model.base import PayBrigde
from pydantic import ConfigDict, Field

logging = logging.getLogger("PayBridge")

class SDKConfig(PayBrigde):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    user_agent: str = "PayBridge SDK/1.0"
    default_timeout: float = 30.0
    max_retries: int = 3
    retry_backoff_factor: float = 0.5
    debug: bool = False
    
    log_level: int = logging.INFO

    def setup_logging(self):
        level = logging.DEBUG if self.debug else self.log_level
        logger.setLevel(level)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)


settings = SDKConfig()