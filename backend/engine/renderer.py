"""
Rendu des résultats de simulation en images PNG.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import List, Tuple

from PIL import Image, ImageDraw, ImageFont

from .geometry import Point, Polygon, bounding_box
from .simulation import Cell, Garden, SunSimulationResult


def _color_for_hours(hours: float, max_hours: float) -> Tuple[int, int, int]:
    """Dégradé rouge (peu de soleil) → jaune → vert (beaucoup de soleil)."""
    if max_hours <= 0:
        return (200, 200, 200)
    ratio = max(0.0, min(1.0, hours / max_hours))
    if ratio < 0.5:
        # rouge (255,0,0) -> jaune (255,255,0)
        t = ratio * 2
        return (255, int(255 * t), 0)
    else:
        # jaune (255,255,0) -> vert (0,255,0)
        t = (ratio - 0.5) * 2
        return (int(255 * (1 - t)), 255, 0)


def render_heatmap(
    result: SunSimulationResult,
    output_path: str,
    width_px: int = 800,
    show_obstacles: bool = True,
    show_grid: bool = False,
) -> None:
    """Génère une heatmap PNG de l'ensoleillement."""
    cells = result.cells
    ny = len(cells)
    nx = len(cells[0])
    max_hours = result.max_sun_hours() or 1.0

    min_x, min_y, max_x, max_y = result.bbox
    world_w = max_x - min_x
    world_h = max_y - min_y

    aspect = world_h / world_w if world_w > 0 else 1.0
    height_px = max(1, int(width_px * aspect))

    img = Image.new("RGB", (width_px, height_px), (245, 245, 240))
    draw = ImageDraw.Draw(img)

    def world_to_px(p: Point) -> Tuple[int, int]:
        x = int((p.x - min_x) / world_w * width_px)
        y = int((max_y - p.y) / world_h * height_px)
        return (x, y)

    # Dessin de la heatmap
    garden_poly = result.garden.footprint()
    cell_w = width_px / nx
    cell_h = height_px / ny
    for j, row in enumerate(cells):
        for i, cell in enumerate(row):
            point = Point(cell.x, cell.y)
            from .geometry import point_in_polygon
            in_garden = point_in_polygon(point, garden_poly)
            if in_garden:
                color = _color_for_hours(cell.sun_hours, max_hours)
            else:
                color = (230, 230, 225)
            x0 = int(i * cell_w)
            y0 = int(j * cell_h)
            x1 = int((i + 1) * cell_w)
            y1 = int((j + 1) * cell_h)
            draw.rectangle([x0, y0, x1, y1], fill=color)
            if show_grid and in_garden:
                draw.rectangle([x0, y0, x1, y1], outline=(255, 255, 255, 80))

    # Contour du potager
    garden_poly = result.garden.footprint()
    draw.polygon([world_to_px(p) for p in garden_poly.points], outline=(30, 60, 40), width=3)

    # Obstacles
    if show_obstacles:
        for obstacle in result.garden.obstacles:
            foot = obstacle.footprint(Point(0, 0))
            draw.polygon([world_to_px(p) for p in foot.points], fill=(100, 70, 50), outline=(60, 40, 30))

    # Légende et infos
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except Exception:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    info_lines = [
        f"Jour: {result.day.isoformat()}",
        f"Ensoleillement max: {max_hours:.1f}h / {result.total_daylight_hours:.1f}h",
        f"Ensoleillement moyen: {result.average_sun_hours():.1f}h",
        f"Résolution: {nx}x{ny}  |  Pas: {result.step_minutes}min",
    ]
    y_offset = 10
    for line in info_lines:
        draw.text((12, y_offset), line, fill=(30, 30, 30), font=font)
        y_offset += 18

    # Échelle de couleur
    bar_x = width_px - 120
    bar_y = 10
    bar_w = 20
    bar_h = 150
    for y in range(bar_h):
        h = max_hours * (1 - y / bar_h)
        color = _color_for_hours(h, max_hours)
        draw.line([(bar_x, bar_y + y), (bar_x + bar_w, bar_y + y)], fill=color)
    draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], outline=(50, 50, 50))
    draw.text((bar_x + bar_w + 6, bar_y), f"{max_hours:.1f}h", fill=(30, 30, 30), font=small_font)
    draw.text((bar_x + bar_w + 6, bar_y + bar_h - 12), "0h", fill=(30, 30, 30), font=small_font)

    img.save(output_path)


def render_shadow_frame(
    result: SunSimulationResult,
    sun_index: int,
    output_path: str,
    width_px: int = 800,
) -> None:
    """Génère une image de l'ombre à un instant donné."""
    dt, sun_pos = result.positions[sun_index]
    cells = result.cells
    ny = len(cells)
    nx = len(cells[0])

    min_x, min_y, max_x, max_y = result.bbox
    world_w = max_x - min_x
    world_h = max_y - min_y
    aspect = world_h / world_w if world_w > 0 else 1.0
    height_px = max(1, int(width_px * aspect))

    img = Image.new("RGB", (width_px, height_px), (245, 245, 240))
    draw = ImageDraw.Draw(img)

    def world_to_px(p: Point) -> Tuple[int, int]:
        x = int((p.x - min_x) / world_w * width_px)
        y = int((max_y - p.y) / world_h * height_px)
        return (x, y)

    # Ombres à cet instant
    garden_center = Point(0, 0)
    shadow_polys: List[Polygon] = []
    for obstacle in result.garden.obstacles:
        shadow = obstacle.shadow(garden_center, sun_pos.azimuth, sun_pos.altitude)
        if shadow:
            shadow_polys.append(shadow)

    garden_poly = result.garden.footprint()

    # Cellules
    cell_w = width_px / nx
    cell_h = height_px / ny
    for j, row in enumerate(cells):
        for i, cell in enumerate(row):
            point = Point(cell.x, cell.y)
            in_garden = any(
                # Utilise les mêmes règles que la simulation
                (point.x - p.x) ** 2 + (point.y - p.y) ** 2 < 1e-6
                for p in garden_poly.points
            )
            # Recalcul simple
            from .geometry import point_in_polygon as pip
            in_garden = pip(point, garden_poly)
            in_shadow = any(pip(point, s) for s in shadow_polys)
            color = (180, 220, 180) if in_garden else (245, 245, 240)
            if in_shadow:
                color = (80, 80, 100)
            x0 = int(i * cell_w)
            y0 = int(j * cell_h)
            x1 = int((i + 1) * cell_w)
            y1 = int((j + 1) * cell_h)
            draw.rectangle([x0, y0, x1, y1], fill=color)

    draw.polygon([world_to_px(p) for p in garden_poly.points], outline=(30, 60, 40), width=3)

    for obstacle in result.garden.obstacles:
        foot = obstacle.footprint(garden_center)
        draw.polygon([world_to_px(p) for p in foot.points], fill=(100, 70, 50), outline=(60, 40, 30))

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except Exception:
        font = ImageFont.load_default()

    draw.text(
        (12, 10),
        f"{dt.strftime('%H:%M')}  |  Soleil: alt={sun_pos.altitude:.1f}°, az={sun_pos.azimuth:.1f}°",
        fill=(30, 30, 30),
        font=font,
    )

    img.save(output_path)
