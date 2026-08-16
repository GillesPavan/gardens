"""
Export des résultats de simulation (CSV, JSON, etc.).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Sequence

from .simulation import SunSimulationResult


def export_csv(result: SunSimulationResult, path: str | Path) -> None:
    """Exporte la grille de résultats au format CSV."""
    path = Path(path)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "x_m", "y_m", "sun_hours", "in_garden",
            "day", "step_minutes", "total_daylight_hours",
        ])
        for row in result.cells:
            for cell in row:
                writer.writerow([
                    f"{cell.x:.3f}",
                    f"{cell.y:.3f}",
                    f"{cell.sun_hours:.3f}",
                    "1" if cell.samples > 0 else "0",
                    result.day.isoformat(),
                    result.step_minutes,
                    f"{result.total_daylight_hours:.3f}",
                ])


def export_summary(result: SunSimulationResult, path: str | Path) -> None:
    """Exporte un récapitulatif JSON."""
    path = Path(path)
    summary = {
        "day": result.day.isoformat(),
        "step_minutes": result.step_minutes,
        "grid": result.grid_size,
        "total_daylight_hours": round(result.total_daylight_hours, 3),
        "max_sun_hours": round(result.max_sun_hours(), 3),
        "average_sun_hours": round(result.average_sun_hours(), 3),
        "garden": {
            "length_m": result.garden.length_m,
            "width_m": result.garden.width_m,
            "orientation_deg": result.garden.orientation_deg,
            "bed_height_m": result.garden.bed_height_m,
            "obstacles": [
                {
                    "name": o.name,
                    "distance_m": o.distance_m,
                    "direction_deg": o.direction_deg,
                    "height_m": o.height_m,
                    "width_m": o.width_m,
                    "depth_m": o.depth_m,
                }
                for o in result.garden.obstacles
            ],
        },
    }
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
