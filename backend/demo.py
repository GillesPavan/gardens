#!/usr/bin/env python3
"""
Démonstration du moteur de simulation d'ensoleillement.

Lancez avec:
    cd gardens/backend
    python3 demo.py
"""

from datetime import date
from pathlib import Path

from engine import Garden, Obstacle, run_simulation
from engine.exporter import export_csv, export_summary
from engine.renderer import render_heatmap, render_shadow_frame


def main() -> None:
    # --- Configuration du potager ---
    # Coordonnées de Lyon, France
    latitude = 45.75
    longitude = 4.85

    garden = Garden(
        length_m=4.0,        # côté long
        width_m=3.0,         # côté court
        orientation_deg=0.0, # côté long Nord-Sud
        bed_height_m=0.3,
        obstacles=[
            # Mur au Nord, 2 m du centre, hauteur 1.8 m, largeur 4 m
            Obstacle(name="Mur Nord", distance_m=2.5, direction_deg=0.0, height_m=1.8, width_m=5.0, depth_m=0.2),
            # Arbre à l'Est
            Obstacle(name="Arbre Est", distance_m=5.0, direction_deg=90.0, height_m=4.0, width_m=2.5, depth_m=2.5),
        ],
    )

    # Jour du solstice d'été 2026
    day = date(2026, 6, 21)

    print(f"Simulation pour {day.isoformat()} à Lyon ({latitude}, {longitude})")
    print(f"Potager: {garden.length_m}m x {garden.width_m}m, orientation {garden.orientation_deg}°")
    print(f"Obstacles: {len(garden.obstacles)}")

    result = run_simulation(
        garden=garden,
        latitude=latitude,
        longitude=longitude,
        day=day,
        grid_resolution=50,
        step_minutes=30,
    )

    print(f"Ensoleillement maximal dans le potager: {result.max_sun_hours():.1f} h")
    print(f"Ensoleillement moyen: {result.average_sun_hours():.1f} h")
    print(f"Ensoleillement théorique max: {result.total_daylight_hours:.1f} h")

    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    heatmap_path = output_dir / "heatmap.png"
    render_heatmap(result, str(heatmap_path), width_px=900)
    print(f"Heatmap sauvegardée: {heatmap_path}")

    csv_path = output_dir / "heatmap.csv"
    export_csv(result, str(csv_path))
    print(f"CSV sauvegardé: {csv_path}")

    summary_path = output_dir / "summary.json"
    export_summary(result, str(summary_path))
    print(f"Résumé JSON sauvegardé: {summary_path}")

    # Quelques frames de l'ombre dans la journée
    for idx in [8, 14, 20, 26]:
        if idx < len(result.positions):
            frame_path = output_dir / f"shadow_{idx:02d}.png"
            render_shadow_frame(result, idx, str(frame_path), width_px=900)
            print(f"Frame {idx} sauvegardée: {frame_path}")


if __name__ == "__main__":
    main()
