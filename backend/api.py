"""
Backend FastAPI pour l'outil de modélisation d'ensoleillement.

Endpoints:
    POST /api/analyze-photos   -> extrait les métadonnées des photos uploadées
    POST /api/simulate         -> lance la simulation et retourne les fichiers
"""

from __future__ import annotations

import io
import json
import tempfile
from datetime import date
from pathlib import Path
from typing import List

from PIL import Image, ExifTags
from PIL.ExifTags import GPSTAGS

# Ces imports nécessitent FastAPI/uvicorn (voir requirements.txt)
try:
    from fastapi import FastAPI, File, Form, HTTPException, UploadFile
    from fastapi.responses import FileResponse, JSONResponse
    HAS_FASTAPI = True
except ImportError:  # pragma: no cover
    FastAPI = None
    File = Form = HTTPException = UploadFile = None
    FileResponse = JSONResponse = None
    HAS_FASTAPI = False

from engine import Garden, Obstacle, run_simulation
from engine.exporter import export_csv, export_summary
from engine.renderer import render_heatmap

if HAS_FASTAPI:
    app = FastAPI(title="Gardens Sun Engine")
else:
    app = None


def _get_exif_gps(exif: dict) -> tuple[float, float] | None:
    """Extrait les coordonnées GPS des métadonnées EXIF."""
    if "GPSInfo" not in exif:
        return None
    gps_info = {}
    for key in exif["GPSInfo"].keys():
        decoded = GPSTAGS.get(key, key)
        gps_info[decoded] = exif["GPSInfo"][key]

    def _convert(dms, ref):
        degrees = dms[0]
        minutes = dms[1] / 60.0
        seconds = dms[2] / 3600.0
        value = degrees + minutes + seconds
        if ref in ("S", "W"):
            value = -value
        return value

    try:
        lat = _convert(gps_info["GPSLatitude"], gps_info["GPSLatitudeRef"])
        lon = _convert(gps_info["GPSLongitude"], gps_info["GPSLongitudeRef"])
        return lat, lon
    except (KeyError, TypeError, ZeroDivisionError):
        return None


def _extract_metadata(image_bytes: bytes) -> dict:
    """Extrait les métadonnées utiles d'une photo."""
    img = Image.open(io.BytesIO(image_bytes))
    metadata = {
        "format": img.format,
        "size": img.size,
        "has_exif": False,
        "gps": None,
        "datetime": None,
    }
    try:
        exif = img._getexif()
        if exif:
            metadata["has_exif"] = True
            for tag_id, value in exif.items():
                tag = ExifTags.TAGS.get(tag_id, tag_id)
                if tag == "DateTimeOriginal":
                    metadata["datetime"] = value
            metadata["gps"] = _get_exif_gps(exif)
    except Exception:
        pass
    return metadata


if HAS_FASTAPI:
    @app.post("/api/analyze-photos")
    async def analyze_photos(photos: List[UploadFile] = File(...)):
        """
        Analyse les photos uploadées pour extraire un maximum d'informations.

        Pour l'instant :
        - lecture des métadonnées EXIF (GPS, date)
        - estimation par défaut si pas assez d'infos

        À terme : appel à un modèle de vision pour détecter le potager,
        les obstacles et estimer leurs dimensions.
        """
        if not photos:
            raise HTTPException(status_code=400, detail="Aucune photo fournie")

        all_gps = []
        dates = []
        for photo in photos:
            contents = await photo.read()
            meta = _extract_metadata(contents)
            if meta["gps"]:
                all_gps.append(meta["gps"])
            if meta["datetime"]:
                dates.append(meta["datetime"])

        # Si on a des coordonnées GPS, on fait la moyenne
        if all_gps:
            lat = sum(g[0] for g in all_gps) / len(all_gps)
            lon = sum(g[1] for g in all_gps) / len(all_gps)
        else:
            lat, lon = None, None

        # TODO: intégrer un modèle de vision ici pour détecter automatiquement
        # le potager, les obstacles, leur orientation et leurs dimensions.
        # En attendant, on retourne une estimation par défaut avec les métadonnées brutes.
        return {
            "location": f"{lat:.4f}, {lon:.4f}" if lat is not None else None,
            "latitude": lat,
            "longitude": lon,
            "length": 4.0,
            "width": 3.0,
            "orientation": 0.0,
            "obstacles": [
                {"name": "Obstacle détecté", "type": "mur", "direction": 0, "distance": 2.5, "height": 1.8, "width": 4.0},
            ],
            "confidence": "low",
            "missing": ["dimensions_exactes", "orientation", "obstacles"],
            "metadata": {
                "photo_count": len(photos),
                "gps_found": len(all_gps),
                "dates": dates,
            },
        }

    @app.post("/api/simulate")
    async def simulate(
        location: str = Form(""),
        latitude: float = Form(0.0),
        longitude: float = Form(0.0),
        length_m: float = Form(4.0),
        width_m: float = Form(3.0),
        orientation_deg: float = Form(0.0),
        day: str = Form("2026-06-21"),
        grid_resolution: int = Form(50),
        step_minutes: int = Form(30),
        obstacles_json: str = Form("[]"),
    ):
        """Lance la simulation et retourne les fichiers générés."""
        try:
            obstacles_data = json.loads(obstacles_json)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="obstacles_json invalide")

        obstacles = [
            Obstacle(
                name=o.get("name", "Obstacle"),
                distance_m=o.get("distance_m", 0.0),
                direction_deg=o.get("direction_deg", 0.0),
                height_m=o.get("height_m", 0.0),
                width_m=o.get("width_m", 0.3),
                depth_m=o.get("depth_m", 0.3),
            )
            for o in obstacles_data
        ]

        garden = Garden(
            length_m=length_m,
            width_m=width_m,
            orientation_deg=orientation_deg,
            bed_height_m=0.0,
            obstacles=obstacles,
        )

        sim_day = date.fromisoformat(day)
        result = run_simulation(
            garden=garden,
            latitude=latitude,
            longitude=longitude,
            day=sim_day,
            grid_resolution=grid_resolution,
            step_minutes=step_minutes,
        )

        tmpdir = Path(tempfile.mkdtemp(prefix="gardens-sun-"))
        heatmap_path = tmpdir / "heatmap.png"
        csv_path = tmpdir / "heatmap.csv"
        summary_path = tmpdir / "summary.json"

        render_heatmap(result, str(heatmap_path), width_px=900)
        export_csv(result, str(csv_path))
        export_summary(result, str(summary_path))

        return {
            "heatmap_url": "/api/download/heatmap.png",
            "csv_url": "/api/download/heatmap.csv",
            "summary_url": "/api/download/summary.json",
            "summary": json.loads(summary_path.read_text(encoding="utf-8")),
        }

    @app.get("/")
    async def root():
        return {"message": "Gardens Sun Engine API"}
