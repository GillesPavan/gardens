"""
Géométrie 2D en pure Python pour la projection d'ombres.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List, Sequence


@dataclass(frozen=True)
class Point:
    x: float
    y: float

    def __add__(self, other: Point) -> Point:
        return Point(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Point) -> Point:
        return Point(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> Point:
        return Point(self.x * scalar, self.y * scalar)


@dataclass(frozen=True)
class Segment:
    a: Point
    b: Point


@dataclass(frozen=True)
class Polygon:
    points: Sequence[Point]

    @property
    def segments(self) -> List[Segment]:
        pts = self.points
        return [Segment(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]

    @property
    def area(self) -> float:
        """Aire signée (shoelace)."""
        pts = self.points
        if len(pts) < 3:
            return 0.0
        s = 0.0
        for i in range(len(pts)):
            x1, y1 = pts[i].x, pts[i].y
            x2, y2 = pts[(i + 1) % len(pts)].x, pts[(i + 1) % len(pts)].y
            s += x1 * y2 - x2 * y1
        return abs(s) / 2.0


def point_in_polygon(point: Point, polygon: Polygon) -> bool:
    """Ray-casting : True si le point est dans le polygone."""
    x, y = point.x, point.y
    inside = False
    pts = polygon.points
    n = len(pts)
    j = n - 1
    for i in range(n):
        xi, yi = pts[i].x, pts[i].y
        xj, yj = pts[j].x, pts[j].y
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def segments_intersect(s1: Segment, s2: Segment) -> bool:
    """Test d'intersection de deux segments (orientation)."""

    def orient(a: Point, b: Point, c: Point) -> float:
        return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)

    o1 = orient(s1.a, s1.b, s2.a)
    o2 = orient(s1.a, s1.b, s2.b)
    o3 = orient(s2.a, s2.b, s1.a)
    o4 = orient(s2.a, s2.b, s1.b)

    if o1 * o2 < 0 and o3 * o4 < 0:
        return True

    # Colinéarités aux extrémités (tolérance)
    def on_segment(a: Point, b: Point, c: Point) -> bool:
        return min(a.x, c.x) - 1e-9 <= b.x <= max(a.x, c.x) + 1e-9 and min(a.y, c.y) - 1e-9 <= b.y <= max(a.y, c.y) + 1e-9

    if abs(o1) < 1e-9 and on_segment(s1.a, s2.a, s1.b):
        return True
    if abs(o2) < 1e-9 and on_segment(s1.a, s2.b, s1.b):
        return True
    if abs(o3) < 1e-9 and on_segment(s2.a, s1.a, s2.b):
        return True
    if abs(o4) < 1e-9 and on_segment(s2.a, s1.b, s2.b):
        return True

    return False


def polygon_intersection(p1: Polygon, p2: Polygon) -> Polygon | None:
    """
    Intersection de deux polygones convexes par clipping de Sutherland-Hodgman.
    Retourne None si l'intersection est vide.
    """
    if len(p1.points) < 3 or len(p2.points) < 3:
        return None

    output = list(p1.points)
    clip_edges = p2.segments

    for edge in clip_edges:
        input_list = output
        output = []
        if not input_list:
            return None
        s = input_list[-1]
        for e in input_list:
            if _inside(e, edge):
                if not _inside(s, edge):
                    inter = _compute_intersection(s, e, edge)
                    if inter:
                        output.append(inter)
                output.append(e)
            elif _inside(s, edge):
                inter = _compute_intersection(s, e, edge)
                if inter:
                    output.append(inter)
            s = e
        if not output:
            return None

    if len(output) < 3:
        return None
    return Polygon(output)


def _inside(p: Point, edge: Segment) -> bool:
    """Vérifie si p est à l'intérieur du demi-plan défini par edge (p2 orienté)."""
    a, b = edge.a, edge.b
    cross = (b.x - a.x) * (p.y - a.y) - (b.y - a.y) * (p.x - a.x)
    return cross >= -1e-9


def _compute_intersection(a: Point, b: Point, edge: Segment) -> Point | None:
    """Intersection de la droite (a,b) avec le segment edge."""
    x1, y1 = a.x, a.y
    x2, y2 = b.x, b.y
    x3, y3 = edge.a.x, edge.a.y
    x4, y4 = edge.b.x, edge.b.y

    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-12:
        return None

    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / denom
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / denom
    return Point(px, py)


def shadow_polygon(obstacle: Polygon, sun_azimuth_deg: float, sun_altitude_deg: float) -> Polygon:
    """
    Projette l'ombre d'un polygone sur le sol (z=0).

    Args:
        obstacle: polygone dans le plan vertical (x,y) représentant la base,
                  la hauteur étant implicite (les points ont une hauteur z).
        sun_azimuth_deg: azimut du soleil, 0=Nord, 90=Est
        sun_altitude_deg: élévation du soleil au-dessus de l'horizon

    Note:
        Pour simplifier, on modélise chaque obstacle comme un rectangle vertical
        de hauteur h situé entre (x,y) au sol. Cette fonction suppose que
        obstacle est vu de dessus et que la hauteur est passée séparément.
        Voir simulation.Obstacle pour l'usage concret.
    """
    raise NotImplementedError("Utiliser Obstacle.shadow() dans simulation.py")


def translate_polygon(polygon: Polygon, vector: Point) -> Polygon:
    return Polygon([pt + vector for pt in polygon.points])


def scale_polygon(polygon: Polygon, factor: float, center: Point = Point(0, 0)) -> Polygon:
    return Polygon([center + (pt - center) * factor for pt in polygon.points])


def bounding_box(points: Iterable[Point]) -> tuple[float, float, float, float]:
    pts = list(points)
    if not pts:
        return (0.0, 0.0, 0.0, 0.0)
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def polygon_area(polygon: Polygon) -> float:
    return polygon.area
