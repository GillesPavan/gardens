#!/usr/bin/env python3
"""
Serveur de développement sans dépendances externes.

Implémente les mêmes endpoints que api.py (FastAPI) mais avec
http.server de la bibliothèque standard. Utile pour tester le
frontend sans installer FastAPI/uvicorn.

Usage:
    cd gardens/backend
    python3 dev_server.py
    # ouvre site/app.html dans un navigateur
"""

from __future__ import annotations

import io
import json
import logging
from datetime import date
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from engine import Garden, Obstacle, run_simulation
from engine.exporter import export_csv, export_summary
from engine.renderer import render_heatmap
from api import _extract_metadata  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


def _parse_multipart(body: bytes, content_type: str) -> dict:
    """Parser multipart/form-data minimal (cgi retiré en Python 3.13)."""
    parts: dict = {}
    _, params = content_type.split(";", 1)
    boundary = None
    for p in params.split(";"):
        if "=" in p:
            k, v = p.split("=", 1)
            if k.strip() == "boundary":
                boundary = v.strip().strip('"').encode("utf-8")
    if not boundary:
        return parts

    delimiter = b"--" + boundary
    chunks = body.split(delimiter)
    for chunk in chunks:
        chunk = chunk.strip(b"\r\n")
        if not chunk or chunk == b"--":
            continue
        header_end = chunk.find(b"\r\n\r\n")
        if header_end == -1:
            continue
        headers = chunk[:header_end].decode("utf-8", errors="ignore")
        data = chunk[header_end + 4 :]
        # retire le trailing \r\n final
        if data.endswith(b"\r\n"):
            data = data[:-2]

        name = None
        filename = None
        for line in headers.split("\r\n"):
            if line.lower().startswith("content-disposition"):
                for token in line.split(";"):
                    token = token.strip()
                    if token.startswith("name="):
                        name = token[5:].strip('"')
                    elif token.startswith("filename="):
                        filename = token[9:].strip('"')

        if name:
            if name not in parts:
                parts[name] = []
            parts[name].append({"filename": filename, "data": data})
    return parts


API_PORT = 8765
SITE_DIR = Path(__file__).parent.parent / "site"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SITE_DIR), **kwargs)

    def log_message(self, format, *args):
        logging.info(format % args)

    def _send_json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/analyze-photos":
            self._handle_analyze_photos()
        elif path == "/api/simulate":
            self._handle_simulate()
        else:
            self._send_json(404, {"error": "Not found"})

    def _handle_analyze_photos(self):
        body = self._read_body()
        content_type = self.headers.get("Content-Type", "")

        photos = []
        if "multipart/form-data" in content_type:
            form = _parse_multipart(body, content_type)
            for item in form.get("photos", []):
                photos.append(item["data"])

        if not photos:
            self._send_json(400, {"error": "Aucune photo fournie"})
            return

        all_gps = []
        dates = []
        for photo_bytes in photos:
            meta = _extract_metadata(photo_bytes)
            if meta["gps"]:
                all_gps.append(meta["gps"])
            if meta["datetime"]:
                dates.append(meta["datetime"])

        if all_gps:
            lat = sum(g[0] for g in all_gps) / len(all_gps)
            lon = sum(g[1] for g in all_gps) / len(all_gps)
        else:
            lat, lon = None, None

        self._send_json(200, {
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
        })

    def _handle_simulate(self):
        import base64
        import tempfile

        body = self._read_body()
        content_type = self.headers.get("Content-Type", "")

        if "application/json" in content_type:
            data = json.loads(body.decode("utf-8"))
        elif "application/x-www-form-urlencoded" in content_type:
            params = parse_qs(body.decode("utf-8"))
            data = {k: v[0] for k, v in params.items()}
        else:
            self._send_json(400, {"error": "Content-Type non supporté"})
            return

        try:
            obstacles_data = data.get("obstacles", [])
            if isinstance(obstacles_data, str):
                obstacles_data = json.loads(obstacles_data)

            obstacles = [
                Obstacle(
                    name=o.get("name", "Obstacle"),
                    distance_m=float(o.get("distance_m", 0.0)),
                    direction_deg=float(o.get("direction_deg", 0.0)),
                    height_m=float(o.get("height_m", 0.0)),
                    width_m=float(o.get("width_m", 0.3) or 0.3),
                    depth_m=float(o.get("depth_m", 0.3) or 0.3),
                )
                for o in obstacles_data
            ]

            garden = Garden(
                length_m=float(data.get("length_m", 4.0)),
                width_m=float(data.get("width_m", 3.0)),
                orientation_deg=float(data.get("orientation_deg", 0.0)),
                bed_height_m=0.0,
                obstacles=obstacles,
            )

            sim_day = date.fromisoformat(data.get("day", "2026-06-21"))
            result = run_simulation(
                garden=garden,
                latitude=float(data.get("latitude", 45.75)),
                longitude=float(data.get("longitude", 4.85)),
                day=sim_day,
                grid_resolution=int(data.get("grid_resolution", 50)),
                step_minutes=int(data.get("step_minutes", 30)),
            )

            tmpdir = Path(tempfile.mkdtemp(prefix="gardens-sun-"))
            heatmap_path = tmpdir / "heatmap.png"
            csv_path = tmpdir / "heatmap.csv"
            summary_path = tmpdir / "summary.json"

            render_heatmap(result, str(heatmap_path), width_px=900)
            export_csv(result, str(csv_path))
            export_summary(result, str(summary_path))

            def b64(path: Path) -> str:
                return base64.b64encode(path.read_bytes()).decode("ascii")

            self._send_json(200, {
                "heatmap": {"filename": "heatmap.png", "mime_type": "image/png", "base64": b64(heatmap_path)},
                "csv": {"filename": "heatmap.csv", "mime_type": "text/csv", "base64": b64(csv_path)},
                "summary": {"filename": "summary.json", "mime_type": "application/json", "base64": b64(summary_path)},
                "summary_data": json.loads(summary_path.read_text(encoding="utf-8")),
            })
        except Exception as e:
            logging.exception("Erreur simulation")
            self._send_json(500, {"error": str(e)})


def main():
    server = HTTPServer(("", API_PORT), Handler)
    logging.info(f"Serveur de développement Gardens sur http://localhost:{API_PORT}")
    logging.info(f"Site servi depuis: {SITE_DIR}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
