from __future__ import annotations

import re
from typing import Any

from app.generation.figure_generators import (
    basic_circuit_resistor_svg,
    geometry_shape_svg,
    lever_svg,
)


NUMBER_PATTERN = r"(\d+(?:\.\d+)?)"


def _number_from_match(value: str) -> int | float:
    numeric = float(value)
    if numeric.is_integer():
        return int(numeric)
    return round(numeric, 2)


def _extract_circuit_values(text: str | None) -> tuple[int | float | None, int | float | None]:
    if not text:
        return None, None
    voltage_match = re.search(rf"{NUMBER_PATTERN}\s*(?:v|volt|volts)\b", text, flags=re.IGNORECASE)
    resistance_match = re.search(rf"{NUMBER_PATTERN}\s*(?:-| )?ohm", text, flags=re.IGNORECASE)
    voltage = _number_from_match(voltage_match.group(1)) if voltage_match else None
    resistance = _number_from_match(resistance_match.group(1)) if resistance_match else None
    return voltage, resistance


def _as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def build_question_figure_svg(
    *,
    figure_type: str | None,
    question_text: str,
    figure_alt_text: str | None = None,
    figure_data: dict[str, Any] | None = None,
) -> str | None:
    normalized_type = (figure_type or "").strip().lower()
    metadata = _as_mapping(figure_data)

    if normalized_type == "circuit":
        voltage = metadata.get("voltage")
        resistance = metadata.get("resistance")
        if voltage is None or resistance is None:
            voltage, resistance = _extract_circuit_values(figure_alt_text or "")
        if voltage is None or resistance is None:
            voltage, resistance = _extract_circuit_values(question_text)
        if voltage is None or resistance is None:
            return None
        return basic_circuit_resistor_svg(voltage=voltage, resistance=resistance)

    if normalized_type in {"lever", "mechanical_lever"}:
        effort_distance = metadata.get("effort_distance") or metadata.get("effort") or 4
        load_distance = metadata.get("load_distance") or metadata.get("load") or 2
        return lever_svg(effort_distance=effort_distance, load_distance=load_distance)

    if normalized_type in {"shape", "geometry", "diagram"}:
        shape = str(metadata.get("shape") or "").strip().lower()
        if not shape:
            haystack = f"{figure_alt_text or ''} {question_text}".lower()
            if "triangle" in haystack:
                shape = "triangle"
            elif "rectangle" in haystack or "square" in haystack:
                shape = "rectangle"
            else:
                shape = "circle"
        label = figure_alt_text or "Reference diagram"
        return geometry_shape_svg(shape=shape, label=label)

    return None
