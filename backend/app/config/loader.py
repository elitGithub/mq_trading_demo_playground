"""YAML configuration loader with validation, hot-reload, and history."""

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
import yaml

from app.config.settings import settings

logger = structlog.get_logger()


class ConfigLoader:
    """Loads, validates, and manages YAML configuration files."""

    def __init__(self, config_dir: str | None = None):
        self.config_dir = Path(config_dir or settings.config_dir)
        self.history_dir = self.config_dir / "history"
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, dict[str, Any]] = {}
        self._load_all()

    def _load_all(self) -> None:
        """Load all YAML config files from the config directory."""
        for yaml_file in self.config_dir.glob("*.yaml"):
            name = yaml_file.stem
            self._cache[name] = self._read_yaml(yaml_file)
            logger.info("config.loaded", file=name)

    def _read_yaml(self, path: Path) -> dict[str, Any]:
        """Read and parse a YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        if path.stem == "strategy":
            data = self._normalize_strategy_config(data)
        return data

    @staticmethod
    def _normalize_strategy_config(data: dict[str, Any]) -> dict[str, Any]:
        """Normalize legacy single-strategy config into multi-strategy schema."""
        if not isinstance(data, dict):
            return {}

        if "strategies" in data and isinstance(data.get("strategies"), dict):
            return data

        legacy = data.get("strategy")
        if isinstance(legacy, dict):
            # Poll interval used to live under strategy in legacy schema.
            poll_interval_ms = data.get("poll_interval_ms", legacy.get("poll_interval_ms", 500))
            legacy = dict(legacy)
            legacy.pop("poll_interval_ms", None)
            return {
                "poll_interval_ms": poll_interval_ms,
                "strategies": {"default": legacy},
            }

        return data

    def get(self, name: str) -> dict[str, Any]:
        """Get a config by name (e.g., 'strategy', 'risk')."""
        if name not in self._cache:
            path = self.config_dir / f"{name}.yaml"
            if path.exists():
                self._cache[name] = self._read_yaml(path)
            else:
                return {}
        return self._cache[name]

    def get_nested(self, name: str, *keys: str, default: Any = None) -> Any:
        """Get a nested config value. e.g., get_nested('strategy', 'entry', 'confirmation_candles')"""
        data = self.get(name)
        for key in keys:
            if isinstance(data, dict):
                data = data.get(key)
            else:
                return default
            if data is None:
                return default
        return data

    def reload(self, name: str | None = None) -> None:
        """Reload config from disk. If name is None, reload all."""
        if name:
            path = self.config_dir / f"{name}.yaml"
            if path.exists():
                self._cache[name] = self._read_yaml(path)
                logger.info("config.reloaded", file=name)
        else:
            self._cache.clear()
            self._load_all()

    def update(self, name: str, data: dict[str, Any], changed_by: str = "api") -> None:
        """Update a config file. Saves history before overwriting."""
        path = self.config_dir / f"{name}.yaml"
        self._save_history(name, path)
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        self._cache[name] = data
        logger.info("config.updated", file=name, changed_by=changed_by)

    def _save_history(self, name: str, path: Path) -> None:
        """Save a timestamped copy of the current config before overwriting."""
        if path.exists():
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            dest = self.history_dir / f"{name}.yaml.{ts}"
            shutil.copy2(path, dest)

    def get_history(self, name: str) -> list[dict[str, str]]:
        """List config history snapshots for a given config name."""
        snapshots = []
        for f in sorted(self.history_dir.glob(f"{name}.yaml.*"), reverse=True):
            ts_str = f.suffix.lstrip(".")
            snapshots.append({"filename": f.name, "timestamp": ts_str})
        return snapshots

    def get_enabled_symbols(self) -> list[str]:
        """Get list of enabled symbol names from symbols config."""
        symbols_config = self.get("symbols")
        instruments = symbols_config.get("symbols", {}).get("instruments", {})
        defaults = symbols_config.get("symbols", {}).get("defaults", {})
        default_enabled = defaults.get("enabled", True)
        enabled = []
        for name, cfg in instruments.items():
            if cfg.get("enabled", default_enabled):
                enabled.append(name)
        return enabled

    def is_strategy_enabled(self) -> bool:
        """Check if any strategy under strategies: has enabled: true."""
        strategies = self.get("strategy").get("strategies", {})
        return any(s.get("enabled", False) for s in strategies.values())

    def get_enabled_strategies(self) -> dict[str, dict]:
        """Return dict of all strategies where enabled: true."""
        strategies = self.get("strategy").get("strategies", {})
        return {sid: cfg for sid, cfg in strategies.items() if cfg.get("enabled", False)}

    def get_strategy_for_symbol(self, symbol: str) -> tuple[str, dict] | None:
        """Look up the strategy assigned to a symbol and resolve its config.

        Returns (strategy_id, strategy_config) or None if unresolvable/disabled.
        """
        symbols_cfg = self.get("symbols").get("symbols", {})
        instruments = symbols_cfg.get("instruments", {})
        defaults = symbols_cfg.get("defaults", {})

        sym_cfg = instruments.get(symbol, {})
        strategy_id = sym_cfg.get("strategy", defaults.get("strategy"))
        if not strategy_id:
            return None

        strategies = self.get("strategy").get("strategies", {})
        strategy_cfg = strategies.get(strategy_id)
        if not strategy_cfg or not strategy_cfg.get("enabled", False):
            return None

        return (strategy_id, strategy_cfg)


# Global instance
config_loader = ConfigLoader()
