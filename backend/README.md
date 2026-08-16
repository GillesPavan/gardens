# Gardens — Moteur de simulation d'ensoleillement

Moteur Python autonome qui calcule l'ensoleillement d'un carré potager en fonction de sa localisation, de ses dimensions, de son orientation et des obstacles environnants.

## Objectif

Fournir un pipeline automatisé, sans Blender, capable de :
- calculer la position du soleil à n'importe quelle date/heure
- projeter les ombres des obstacles sur le potager
- générer une heatmap d'ensoleillement
- exporter les résultats en PNG/CSV/JSON
- s'intégrer à une application web via une API FastAPI

## Structure

```
backend/
├── engine/
│   ├── __init__.py
│   ├── sun.py           # Calculs astronomiques de la position du soleil
│   ├── geometry.py      # Géométrie 2D (polygones, intersections, ombres)
│   ├── simulation.py    # Orchestration de la simulation
│   ├── renderer.py      # Rendu des heatmaps et frames
│   └── exporter.py      # Export CSV/JSON
├── api.py               # API FastAPI (upload de photos + simulation)
├── demo.py              # Exemple de simulation en ligne de commande
├── output/              # Résultats générés (ignoré par git)
├── requirements.txt
└── README.md
```

## Installation

Le moteur de base fonctionne avec la **bibliothèque standard Python** et **Pillow**.
L'API web nécessite **FastAPI** et **uvicorn**.

```bash
cd gardens/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> Sur Debian/Ubuntu récent, l'environnement système est `externally-managed` : utilise obligatoirement un venv.

## Utilisation

### Démonstration en ligne de commande

```bash
cd gardens/backend
python3 demo.py
```

> `demo.py` fonctionne avec seulement Pillow (déjà présent sur la plupart des systèmes).

### Développement frontend-backend (sans FastAPI)

Pour tester `site/app.html` connecté aux endpoints sans installer de dépendances :

```bash
cd gardens/backend
python3 dev_server.py
```

Puis ouvrir `http://localhost:8765/app.html` dans un navigateur.

Le serveur de développement utilise uniquement la bibliothèque standard + Pillow.

Génère dans `output/` :
- `heatmap.png` : heatmap d'ensoleillement
- `heatmap.csv` : grille de points exportée
- `summary.json` : récapitulatif JSON
- `shadow_XX.png` : frames de l'ombre à différents moments

### API web (FastAPI)

```bash
cd gardens/backend
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

Endpoints :

- `POST /api/analyze-photos` — upload de photos, extraction EXIF GPS + estimation par défaut
- `POST /api/simulate` — lance la simulation et retourne les métadonnées des fichiers générés
- `GET /` — message de bienvenue

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
- Intégrer un modèle de vision dans `/api/analyze-photos` pour détecter automatiquement les obstacles et leurs dimensions.
- Stocker les résultats côté serveur et proposer des URLs de téléchargement persistantes.
- Déployer le backend sur `gardens.adaequa.com`.
