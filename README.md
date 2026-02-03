# Rectify Perspective

Application de correction de perspective pour images mal scannées (documents, photos). Interface graphique PySide6 avec détection automatique des coins, retouche manuelle, et traitement par lots.

## Prérequis

- **Windows 10/11**
- **Python 3.11+**

## Installation

1. Ouvrir un terminal (PowerShell ou CMD) dans le dossier du projet.
2. Exécuter :
   ```
   install.bat
   ```
3. Attendre le message « Installation OK ».

## Lancement

```
run.bat
```

Le terminal ne s'affiche pas (lancement via `pythonw`). Pour déboguer avec console visible :
```
run_debug.bat
```

Ou manuellement :
```
.venv\Scripts\activate
python -m rectify_gui
```

## Structure du projet

```
rectify_perspective/
├── rectify_gui/
│   ├── app.py          # Point d'entrée
│   ├── ui_main.py      # Interface graphique
│   ├── image_ops.py    # Détection, warp, améliorations
│   ├── io_meta.py      # Chargement/sauvegarde, EXIF/ICC
│   ├── models.py       # Queue, statuts
│   └── utils_geom.py   # Géométrie
├── input/              # Dossier d'entrée (images à traiter)
├── output/             # Dossier de sortie (images rectifiées)
├── requirements.txt
├── install.bat
├── run.bat
└── README.md
```

## Utilisation

### File d'attente (panneau gauche)

- **Drag & drop** : Glisser des images depuis l’explorateur Windows vers la liste.
- **Ajouter fichiers…** : Sélectionner des fichiers.
- **Ajouter dossier input…** : Ouvrir un dialogue pour choisir un dossier à scanner.
- **Remplir depuis input/** : Charger directement toutes les images du dossier `input/`.
- **Retirer sélection** : Supprimer l’élément sélectionné (raccourci **Del**).
- **Vider queue** : Vider toute la file.

### Zone centrale

- **Image** : Affichage avec quadrilatère détecté et 4 poignées déplaçables.
- **Preview** : Aperçu du résultat après warp et post-traitement.
- **Zoom** :
  - Molette : zoom centré sur le curseur.
  - Boutons **−** / **Ajuster** / **+** : zoom arrière, ajuster à la fenêtre, zoom avant.
  - Raccourcis : **Ctrl++** / **Ctrl+=** (zoom avant), **Ctrl+-** (zoom arrière), **Ctrl+0** (ajuster).
- **Pan** : Clic milieu ou clic gauche + glisser (hors des poignées).

### Boutons

| Bouton | Raccourci | Action |
|--------|-----------|--------|
| Auto | A | Relance la détection automatique des coins |
| Reset | R | Réinitialise aux coins auto ou par défaut |
| Valider & Enregistrer | Entrée | Sauvegarde dans `output/` et passe à la suivante |
| Passer | — | Passe à l’image suivante sans sauvegarder |
| Précédent | ← | Image précédente |
| Suivant | → | Image suivante |
| Zoom + | Ctrl++ / Ctrl+= | Zoom avant |
| Zoom − | Ctrl+- | Zoom arrière |
| Ajuster | Ctrl+0 | Ajuster l'image à la fenêtre |

### Options de rendu (panneau droit)

- **Réduction du bruit (NLM)**  
  Réduit le grain/bruit (utile pour scans ou photos en faible lumière).  
  Algorithme Non-Local Means : lisse en préservant les contours.  
  *Intensité 5–20* : plus élevé = lissage plus fort (défaut 10).

- **Amélioration du contraste (CLAHE)**  
  Renforce le contraste local (documents ternes, scans peu contrastés).  
  *Limite de clip 1.0–4.0* : contrôle l’amplification (défaut 2.0).

- **Accentuation (Unsharp Mask)**  
  Rend les contours plus nets (texte, détails).  
  *Intensité 0–2* : 0 = aucun, 1.2 = modéré, >1.5 = marqué.

- **Limiter le changement de taille**  
  Évite les sorties trop grandes ou trop petites.  
  *Facteur max 1.25* : dimension max = original × 1.25.  
  *min_scale_factor* : 0.75 (évite les sorties trop petites).

## Formats supportés

- Entrée : JPG, JPEG, PNG, TIFF, TIF
- Sortie : Même format que l’entrée
- Nom de sortie : `nom_original_rectified.ext`

## Métadonnées

- **JPEG** : EXIF (orientation remise à 1) et profil ICC conservés via `piexif` et Pillow.
- **PNG/TIFF** : Profil ICC conservé. EXIF sur PNG/TIFF non géré (limitation connue).

## Limites connues

1. **EXIF sur PNG/TIFF** : Non copié (format complexe).
2. **Détection auto** : Peut échouer sur images très bruitées ou sans document net ; ajustement manuel possible.
3. **Preview** : Calculé à la résolution complète ; peut être lent sur très grandes images.

## Dépannage

- **« Module not found »** : Vérifier que `install.bat` a bien créé `.venv` et installé les dépendances.
- **Images non chargées** : Vérifier les extensions (jpg, png, tiff).
- **Erreur EXIF** : L’application continue sans EXIF si `piexif` échoue.
