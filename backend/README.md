# Gardens — Moteur de simulation d'ensoleillement

Moteur Python autonome qui calcule l'ensoleillement d'un carré potager en fonction de sa localisation, de ses dimensions, de son orientation et des obstacles environnants.

## Objectif

Fournir un pipeline automatisé, sans Blender, capable de :
- calculer la position du soleil à n'importe quelle date/heure
- projeter les ombres des obstacles sur le potager
- générer une heatmap d'ensoleillement
- exporter les résultats en PNG/CSV

## Structure

```
backend/
├── engine/
│   ├── __init__.py
│   ├── sun.py           # Calculs astronomiques de la position du soleil
│   ├── geometry.py      # Géométrie 2D (polygones, intersections, ombres)
│   ├── simulation.py    # Orchestration de la simulation
│   └── renderer.py      # Rendu des heatmaps et frames
├── demo.py              # Exemple de simulation
├── output/              # Résultats générés
├── requirements.txt
└── README.md
```

## Dépendances

Le moteur fonctionne principalement avec la **bibliothèque standard Python** et **Pillow** pour le rendu.

```bash
pip install -r requirements.txt
```

> Sur Debian/Ubuntu récent, préférez un environnement virtuel (`python3 -m venv .venv`) car l'environnement système est `externally-managed`.

## Utilisation

### Démonstration

```bash
cd gardens/backend
python3 demo.py
```

Génère dans `output/` :
- `heatmap.png` : heatmap d'ensoleillement
- `shadow_XX.png` : frames de l'ombre à différents moments de la journée

### API Python

```python
from datetime import date
from engine import Garden, Obstacle, run_simulation
from engine.renderer import render_heatmap

garden = Garden(
    length_m=4.0,
    width_m=3.0,
    orientation_deg=0.0,
    obstacles=[
        Obstacle(name="Mur Nord", distance_m=2.5, direction_deg=0.0, height_m=1.8, width_m=5.0),
        Obstacle(name="Arbre Est", distance_m=5.0, direction_deg=90.0, height_m=4.0, width_m=2.5),
    ],
)

result = run_simulation(
    garden=garden,
    latitude=45.75,
    longitude=4.85,
    day=date(2026, 6, 21),
    grid_resolution=50,
    step_minutes=30,
)

render_heatmap(result, "output/ma_heatmap.png")
```

## Conventions

- **Coordonnées** : système métrique, origine au centre du potager.
- **Orientation** : `orientation_deg=0` signifie que le côté long est orienté Nord-Sud. `90` = Est-Ouest.
- **Direction des obstacles** : `direction_deg=0` = Nord, `90` = Est, `180` = Sud, `270` = Ouest.
- **Azimut solaire** : `0` = Nord, `90` = Est, etc.

## Améliorations futures

- Remplacer l'implémentation stdlib du soleil par `astral`.
- Remplacer la géométrie maison par `shapely` pour plus de robustesse.
- Ajouter un export CSV et PDF.
- Ajouter un endpoint FastAPI pour intégration web.
