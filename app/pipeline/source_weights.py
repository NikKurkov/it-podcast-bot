from pathlib import Path

from app.config.settings import settings


def load_source_weights(path: str | None = None) -> dict[str, float]:
    weights_path = Path(path or settings.source_weights_file)
    if not weights_path.exists():
        return {}

    weights: dict[str, float] = {}
    for raw_line in weights_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if "=" not in line:
            continue
        raw_source, raw_weight = line.split("=", 1)
        source = raw_source.strip().lstrip("@")
        if not source:
            continue
        try:
            weight = float(raw_weight.strip())
        except ValueError:
            continue
        weights[source.casefold()] = weight

    return weights


def get_source_weight(source_username: str | None, weights: dict[str, float]) -> float:
    if not source_username:
        return 1.0
    return weights.get(source_username.strip().lstrip("@").casefold(), 1.0)
