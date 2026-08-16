"""
Calculs astronomiques de la position du soleil.

Implémentation en pure Python (stdlib) basée sur les algorithmes
de la NOAA Solar Calculations.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from typing import Tuple


@dataclass(frozen=True)
class SunPosition:
    """Position du soleil à un instant donné."""

    altitude: float  # élévation au-dessus de l'horizon, en degrés
    azimuth: float   # azimut, 0° = Nord, 90° = Est, 180° = Sud, 270° = Ouest
    zenith: float    # angle zénithal, en degrés


# Constantes de l'algorithme NOAA
_DEG2RAD = math.pi / 180.0
_RAD2DEG = 180.0 / math.pi


def _to_julian_day(dt: datetime) -> float:
    """Convertit un datetime UTC en jour julien."""
    # Algorithme simplifié, précision suffisante pour notre usage.
    y = dt.year
    m = dt.month
    d = dt.day + (dt.hour + dt.minute / 60.0 + dt.second / 3600.0) / 24.0
    if m <= 2:
        y -= 1
        m += 12
    a = int(y / 100)
    b = 2 - a + int(a / 4)
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + b - 1524.5


def _sun_position_utc(latitude: float, longitude: float, dt: datetime) -> SunPosition:
    """Calcule la position du soleil pour une localisation et un instant UTC."""
    jd = _to_julian_day(dt)
    n = jd - 2451545.0

    # Anomalie moyenne du soleil
    mean_anomaly = (357.52911 + 0.98560028147 * n) % 360.0
    mean_rad = mean_anomaly * _DEG2RAD

    # Équation du centre
    eq_center = (
        1.914602 * math.sin(mean_rad)
        + 0.019993 * math.sin(2 * mean_rad)
        + 0.000289 * math.sin(3 * mean_rad)
    )

    # Longitude écliptique apparente
    sun_lon = (mean_anomaly + eq_center + 102.9372 + 180.0) % 360.0
    sun_lon_rad = sun_lon * _DEG2RAD

    # Déclinaison
    obliquity = 23.439291 - 0.0000003563 * n
    obl_rad = obliquity * _DEG2RAD
    declination = math.asin(math.sin(obl_rad) * math.sin(sun_lon_rad)) * _RAD2DEG

    # Temps sidéral apparent
    hour_angle = (280.46061837 + 360.98564736629 * n) % 360.0
    # Ajout de la longitude pour obtenir l'angle horaire local
    lon_corrected = (hour_angle + longitude - sun_lon) % 360.0
    if lon_corrected > 180.0:
        lon_corrected -= 360.0
    ha_rad = lon_corrected * _DEG2RAD

    lat_rad = latitude * _DEG2RAD
    dec_rad = declination * _DEG2RAD

    # Hauteur du soleil
    sin_alt = math.sin(lat_rad) * math.sin(dec_rad) + math.cos(lat_rad) * math.cos(dec_rad) * math.cos(ha_rad)
    altitude = math.asin(sin_alt) * _RAD2DEG

    # Azimut
    cos_zenith = sin_alt
    sin_zenith = math.sqrt(1 - cos_zenith * cos_zenith)

    if sin_zenith == 0:
        azimuth = 0.0
    else:
        sin_az = -math.sin(ha_rad) * math.cos(dec_rad) / sin_zenith
        cos_az = (math.sin(dec_rad) - math.sin(lat_rad) * cos_zenith) / (math.cos(lat_rad) * sin_zenith)
        az_rad = math.atan2(sin_az, cos_az)
        azimuth = (az_rad * _RAD2DEG) % 360.0

    zenith = 90.0 - altitude
    return SunPosition(altitude=altitude, azimuth=azimuth, zenith=zenith)


def get_sun_position(
    latitude: float,
    longitude: float,
    dt: datetime,
    tz: tzinfo | None = None,
) -> SunPosition:
    """
    Position du soleil.

    Args:
        latitude: degrés décimaux, positif au Nord
        longitude: degrés décimaux, positif à l'Est
        dt: datetime local ou UTC
        tz: fuseau horaire du datetime (si None, considère dt comme UTC)
    """
    if dt.tzinfo is None:
        if tz is not None:
            dt = dt.replace(tzinfo=tz)
        else:
            dt = dt.replace(tzinfo=timezone.utc)
    utc_dt = dt.astimezone(timezone.utc) if dt.tzinfo else dt
    return _sun_position_utc(latitude, longitude, utc_dt.replace(tzinfo=None))


def list_day_positions(
    latitude: float,
    longitude: float,
    day: date,
    step_minutes: int = 30,
    tz: tzinfo | None = None,
) -> list[Tuple[datetime, SunPosition]]:
    """Liste les positions du soleil sur une journée avec un pas de temps donné."""
    positions: list[Tuple[datetime, SunPosition]] = []
    for minutes in range(0, 24 * 60, step_minutes):
        h = minutes // 60
        m = minutes % 60
        local_dt = datetime.combine(day, time(h, m))
        pos = get_sun_position(latitude, longitude, local_dt, tz=tz)
        positions.append((local_dt, pos))
    return positions


def get_daylight_hours(
    latitude: float,
    longitude: float,
    day: date,
    tz: tzinfo | None = None,
) -> Tuple[datetime, datetime]:
    """Retourne (lever, coucher) approximatifs du soleil pour le jour donné."""
    from datetime import timezone as _timezone

    # On cherche les transitions altitude=0 par dichotomie grossière sur la journée.
    positions = list_day_positions(latitude, longitude, day, step_minutes=15, tz=tz)
    above = [p for p in positions if p[1].altitude > 0]
    if not above:
        # Soleil toujours au-dessus ou toujours en dessous
        return (positions[0][0], positions[0][0])
    sunrise = above[0][0]
    sunset = above[-1][0]
    return sunrise, sunset
