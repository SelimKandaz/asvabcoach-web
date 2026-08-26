from __future__ import annotations


def basic_circuit_resistor_svg(*, voltage: int | float, resistance: int | float) -> str:
    return f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 220" role="img" aria-label="Simple circuit with one resistor">
  <rect x="40" y="70" width="90" height="80" rx="10" fill="#f7f3ea" stroke="#574b3f" stroke-width="3"/>
  <text x="85" y="110" text-anchor="middle" font-family="Arial, sans-serif" font-size="22" fill="#574b3f">Battery</text>
  <line x1="130" y1="110" x2="210" y2="110" stroke="#574b3f" stroke-width="5"/>
  <rect x="210" y="85" width="120" height="50" rx="8" fill="#fff" stroke="#574b3f" stroke-width="3"/>
  <text x="270" y="117" text-anchor="middle" font-family="Arial, sans-serif" font-size="20" fill="#574b3f">{resistance} Ω</text>
  <line x1="330" y1="110" x2="520" y2="110" stroke="#574b3f" stroke-width="5"/>
  <line x1="520" y1="110" x2="520" y2="170" stroke="#574b3f" stroke-width="5"/>
  <line x1="520" y1="170" x2="40" y2="170" stroke="#574b3f" stroke-width="5"/>
  <line x1="40" y1="170" x2="40" y2="110" stroke="#574b3f" stroke-width="5"/>
  <text x="450" y="70" font-family="Arial, sans-serif" font-size="18" fill="#574b3f">V = {voltage} V</text>
</svg>
""".strip()


def geometry_shape_svg(*, shape: str, label: str) -> str:
    if shape == "rectangle":
        body = '<rect x="150" y="50" width="220" height="120" fill="#f8f4ed" stroke="#574b3f" stroke-width="4"/>'
    elif shape == "triangle":
        body = '<polygon points="260,40 380,170 140,170" fill="#f8f4ed" stroke="#574b3f" stroke-width="4"/>'
    else:
        body = '<circle cx="260" cy="110" r="70" fill="#f8f4ed" stroke="#574b3f" stroke-width="4"/>'
    return f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 220" role="img" aria-label="{label}">
  {body}
  <text x="260" y="205" text-anchor="middle" font-family="Arial, sans-serif" font-size="18" fill="#574b3f">{label}</text>
</svg>
""".strip()


def lever_svg(*, effort_distance: int | float, load_distance: int | float) -> str:
    return f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 220" role="img" aria-label="Simple lever diagram">
  <line x1="80" y1="150" x2="500" y2="150" stroke="#574b3f" stroke-width="8" stroke-linecap="round"/>
  <polygon points="260,150 300,150 280,105" fill="#cf7d24"/>
  <circle cx="120" cy="150" r="28" fill="#f8f4ed" stroke="#574b3f" stroke-width="4"/>
  <circle cx="440" cy="150" r="28" fill="#f8f4ed" stroke="#574b3f" stroke-width="4"/>
  <text x="120" y="108" text-anchor="middle" font-family="Arial, sans-serif" font-size="18" fill="#574b3f">Effort {effort_distance}</text>
  <text x="440" y="108" text-anchor="middle" font-family="Arial, sans-serif" font-size="18" fill="#574b3f">Load {load_distance}</text>
</svg>
""".strip()
