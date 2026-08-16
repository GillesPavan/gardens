"""
Moteur de simulation d'ensoleillement d'un carré potager.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Callable, List, Sequence, Tuple

from .geometry import (
    Point,
    Polygon,
    bounding_box,
    point_in_polygon,
    polygon_intersection,
    translate_polygon,
)
from .sun import SunPosition, get_sun_position, list_day_positions


_DEG2RAD = math.pi / 180.0


def _azimuth_to_vector(azimuth_deg: float) -> Point:
    """Convertit un azimut (0=Nord, 90=Est) en vecteur horizontal (x=Est, y=Nord)."""
    rad = (90.0 - azimuth_deg) * _DEG2RAD
    return Point(math.cos(rad), math.sin(rad))


def _obstacle_footprint(center: Point, width: float, depth: float, direction_deg: float) -> Polygon:
    """Rectangle au sol orienté dans une direction donnée."""
    # direction_deg: 0=Nord, 90=Est
    rad = (90.0 - direction_deg) * _DEG2RAD
    dx = math.cos(rad) * width / 2.0
    dy = math.sin(rad) * width / 2.0
    perp_rad = rad + math.pi / 2.0
    pdx = math.cos(perp_rad) * depth / 2.0
    pdy = math.sin(perp_rad) * depth / 2.0

    corners = [
        Point(center.x - dx - pdx, center.y - dy - pdy),
        Point(center.x + dx - pdx, center.y + dy - pdy),
        Point(center.x + dx + pdx, center.y + dy + pdy),
        Point(center.x - dx + pdx, center.y - dy + pdy),
    ]
    return Polygon(corners)


@dataclass
class Obstacle:
    """Obstacle projetant une ombre sur le potager."""

    name: str
    distance_m: float      # distance du centre du potager
    direction_deg: float   # 0=Nord, 90=Est, 180=Sud, 270=Ouest
    height_m: float        # hauteur
    width_m: float = 0.3   # largeur au sol
    depth_m: float = 0.3   # profondeur au sol

    def footprint(self, garden_center: Point) -> Polygon:
        """Polygone au sol de l'obstacle."""
        direction_rad = (90.0 - self.direction_deg) * _DEG2RAD
        center = Point(
            garden_center.x + math.cos(direction_rad) * self.distance_m,
            garden_center.y + math.sin(direction_rad) * self.distance_m,
        )
        return _obstacle_footprint(center, self.width_m, self.depth_m, self.direction_deg)

    def shadow(self, garden_center: Point, sun_azimuth_deg: float, sun_altitude_deg: float) -> Polygon | None:
        """Polygone d'ombre projeté au sol par l'obstacle."""
        if sun_altitude_deg <= 0:
            return None
        footprint = self.footprint(garden_center)
        # Longueur de l'ombre au sol = h / tan(altitude)
        shadow_len = self.height_m / math.tan(sun_altitude_deg * _DEG2RAD)
        if shadow_len <= 1e-6:
            return None

        sun_vec = _azimuth_to_vector(sun_azimuth_deg)
        shadow_points: List[Point] = []
        # L'ombre est la forme de l'obstacle translatée dans la direction opposée au soleil.
        for pt in footprint.points:
            shadow_tip = Point(
                pt.x - sun_vec.x * shadow_len,
                pt.y - sun_vec.y * shadow_len,
            )
            shadow_points.append(shadow_tip)

        # Enveloppe convexe = union des points de l'obstacle et de leurs projections
        # Pour un polygone convexe au sol, l'ombre est le polygone formé par les points
        # du bord éclairé + leurs projections.
        all_points = list(footprint.points) + shadow_points
        return Polygon(_convex_hull(all_points))


def _convex_hull(points: Sequence[Point]) -> Sequence[Point]:
    """Calcul de l'enveloppe convexe (Andrew's monotone chain)."""
    pts = sorted(set((p.x, p.y) for p in points))
    if len(pts) <= 1:
        return [Point(x, y) for x, y in pts]

    def cross(o: Tuple[float, float], a: Tuple[float, float], b: Tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: List[Tuple[float, float]] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 1e-9:
            lower.pop()
        lower.append(p)

    upper: List[Tuple[float, float]] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 1e-9:
            upper.pop()
        upper.append(p)

    return [Point(x, y) for x, y in lower[:-1] + upper[:-1]]


@dataclass
class Garden:
    """Description du carré potager."""

    length_m: float      # côté long
    width_m: float       # côté court
    orientation_deg: float = 0.0  # angle du côté long par rapport au Nord, 0=Nord-Sud
    bed_height_m: float = 0.0     # hauteur des bords (optionnel)
    obstacles: List[Obstacle] = field(default_factory=list)

    def footprint(self, center: Point = Point(0, 0)) -> Polygon:
        """Polygone du potager centré sur (0,0) et orienté."""
        # Orientation 0° = côté long Nord-Sud
        # On part d'un rectangle centré, côté long suivant y
        rad = -self.orientation_deg * _DEG2RAD
        cos_o = math.cos(rad)
        sin_o = math.sin(rad)

        half_l = self.length_m / 2.0
        half_w = self.width_m / 2.0

        raw = [
            Point(-half_w, -half_l),
            Point(half_w, -half_l),
            Point(half_w, half_l),
            Point(-half_w, half_l),
        ]

        rotated = []
        for pt in raw:
            rx = pt.x * cos_o - pt.y * sin_o
            ry = pt.x * sin_o + pt.y * cos_o
            rotated.append(Point(center.x + rx, center.y + ry))
        return Polygon(rotated)


@dataclass
class Cell:
    """Cellule de la grille de simulation."""

    x: float
    y: float
    sun_hours: float = 0.0
    samples: int = 0

    def add_sample(self, is_sunny: bool, duration_hours: float) -> None:
        if is_sunny:
            self.sun_hours += duration_hours
        self.samples += 1


@dataclass
class SunSimulationResult:
    """Résultat d'une simulation."""

    garden: Garden
    day: date
    step_minutes: int
    cells: List[List[Cell]]
    bbox: Tuple[float, float, float, float]
    positions: List[Tuple[datetime, SunPosition]]
    total_daylight_hours: float

    @property
    def grid_size(self) -> Tuple[int, int]:
        return len(self.cells[0]), len(self.cells)

    def max_sun_hours(self) -> float:
        return max(cell.sun_hours for row in self.cells for cell in row)

    def average_sun_hours(self) -> float:
        total = sum(cell.sun_hours for row in self.cells for cell in row)
        n = len(self.cells) * len(self.cells[0])
        return total / n if n else 0.0


def run_simulation(
    garden: Garden,
    latitude: float,
    longitude: float,
    day: date,
    grid_resolution: int = 40,
    step_minutes: int = 30,
    tz: timezone | None = None,
) -> SunSimulationResult:
    """
    Lance une simulation d'ensoleillement sur une journée.

    Args:
        garden: description du potager
        latitude, longitude: localisation
        day: jour de simulation
        grid_resolution: nombre de cellules sur le plus petit côté
        step_minutes: pas de temps en minutes
        tz: fuseau horaire (par défaut UTC)
    """
    if tz is None:
        tz = timezone.utc

    positions = list_day_positions(latitude, longitude, day, step_minutes=step_minutes, tz=tz)
    daylight = [p for p in positions if p[1].altitude > 0]
    total_daylight = len(daylight) * step_minutes / 60.0

    # Construction de la grille couvrant le potager
    garden_center = Point(0, 0)
    garden_poly = garden.footprint(garden_center)
    min_x, min_y, max_x, max_y = bounding_box(garden_poly.points)

    # Garder un peu de marge
    margin = max(garden.length_m, garden.width_m) * 0.1
    min_x -= margin
    min_y -= margin
    max_x += margin
    max_y += margin

    width = max_x - min_x
    height = max_y - min_y
    aspect = height / width if width > 0 else 1.0

    nx = grid_resolution
    ny = max(1, int(round(grid_resolution * aspect)))

    cells: List[List[Cell]] = []
    for j in range(ny):
        row: List[Cell] = []
        for i in range(nx):
            x = min_x + (i + 0.5) * width / nx
            y = min_y + (j + 0.5) * height / ny
            row.append(Cell(x=x, y=y))
        cells.append(row)

    duration_hours = step_minutes / 60.0

    # Pour chaque pas de temps ensoleillé, déterminer quelles cellules sont à l'ombre
    for _, sun_pos in daylight:
        shadows: List[Polygon] = []
        for obstacle in garden.obstacles:
            shadow = obstacle.shadow(garden_center, sun_pos.azimuth, sun_pos.altitude)
            if shadow:
                shadows.append(shadow)

        for row in cells:
            for cell in row:
                point = Point(cell.x, cell.y)
                # À l'ombre si dans l'ombre d'un obstacle ET dans le potager
                in_garden = point_in_polygon(point, garden_poly)
                in_shadow = any(point_in_polygon(point, s) for s in shadows)
                is_sunny = in_garden and not in_shadow
                cell.add_sample(is_sunny, duration_hours)

    return SunSimulationResult(
        garden=garden,
        day=day,
        step_minutes=step_minutes,
        cells=cells,
        bbox=(min_x, min_y, max_x, max_y),
        positions=positions,
        total_daylight_hours=total_daylight,
    )
