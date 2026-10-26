from logging import getLogger
from pathlib import Path

import yaml

from src.models.core.trend_signal import TrendSignal

logger = getLogger(__name__)


class TrendSignalRepository:
    """The trend signals in data/trends/, one YAML each (docs/decisions/trends.md)."""

    def __init__(
        self,
        signals_path: str = "data/trends",
    ):
        self.signals_path = Path(signals_path)

    def list(self) -> list[TrendSignal]:

        signals = []

        for file in sorted(self.signals_path.glob("*.yaml")):

            with open(file, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            signals.append(TrendSignal(**data))

        # Like the sources: a relative path over a missing folder is an
        # empty glob, and an empty list must not pass for "no trends".
        if not signals:
            logger.warning(
                "No trend signal YAMLs found in %s (resolved to %s)",
                self.signals_path,
                self.signals_path.resolve(),
            )

        return signals
