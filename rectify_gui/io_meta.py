"""Chargement/sauvegarde d'images avec préservation EXIF et ICC."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np
from numpy.typing import NDArray
from PIL import Image

logger = logging.getLogger(__name__)

# Import piexif conditionnel (principalement pour JPEG)
try:
    import piexif
    HAS_PIEXIF = True
except ImportError:
    HAS_PIEXIF = False
    logger.warning("piexif non installé: EXIF ne sera pas copié sur JPEG")


@dataclass
class ImageMeta:
    """Métadonnées extraites d'une image."""

    exif_bytes: Optional[bytes] = None
    icc_profile: Optional[bytes] = None
    orientation: int = 1


def load_image_with_meta(path: Path) -> tuple[NDArray[np.uint8], ImageMeta]:
    """
    Charge une image via Pillow, applique l'orientation EXIF, retourne BGR numpy + meta.

    Args:
        path: Chemin vers l'image.

    Returns:
        Tuple (image BGR numpy, ImageMeta).
    """
    pil = Image.open(path)
    pil.load()

    meta = ImageMeta()
    # Récupérer EXIF: pil.info["exif"] est le plus fiable (bytes bruts)
    if "exif" in pil.info:
        meta.exif_bytes = pil.info["exif"]
    elif hasattr(pil, "getexif") and pil.getexif():
        try:
            exif_obj = pil.getexif()
            if hasattr(exif_obj, "tobytes"):
                meta.exif_bytes = exif_obj.tobytes()
        except Exception as e:
            logger.debug("Exif bytes non récupérables: %s", e)
    if "icc_profile" in pil.info:
        meta.icc_profile = pil.info["icc_profile"]

    # Orientation EXIF: appliquer la rotation pour afficher "droit"
    try:
        if hasattr(pil, "getexif"):
            exif = pil.getexif()
            orientation = exif.get(274, 1)  # 274 = Orientation
            meta.orientation = orientation
            pil = _apply_orientation(pil, orientation)
    except Exception as e:
        logger.debug("Orientation EXIF non appliquée: %s", e)

    # Convertir en RGB puis BGR pour OpenCV
    if pil.mode == "RGBA":
        pil = pil.convert("RGB")
    elif pil.mode != "RGB":
        pil = pil.convert("RGB")

    arr = np.array(pil)
    bgr = arr[:, :, ::-1].copy()
    return bgr, meta


def _apply_orientation(pil: Image.Image, orientation: int) -> Image.Image:
    """Applique la rotation selon l'orientation EXIF."""
    if orientation == 1:
        return pil
    if orientation == 2:
        return pil.transpose(Image.FLIP_LEFT_RIGHT)
    if orientation == 3:
        return pil.transpose(Image.ROTATE_180)
    if orientation == 4:
        return pil.transpose(Image.FLIP_TOP_BOTTOM)
    if orientation == 5:
        return pil.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.ROTATE_270)
    if orientation == 6:
        return pil.transpose(Image.ROTATE_270)
    if orientation == 7:
        return pil.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.ROTATE_90)
    if orientation == 8:
        return pil.transpose(Image.ROTATE_90)
    return pil


def save_image_with_meta(
    path_out: Path,
    img_bgr: NDArray[np.uint8],
    meta: ImageMeta,
    quality: int = 95,
    suffix: str = "_rectified",
) -> None:
    """
    Sauvegarde l'image avec EXIF (orientation=1) et ICC si possible.

    Args:
        path_out: Chemin de sortie (peut inclure le suffix dans le nom).
        img_bgr: Image BGR numpy.
        meta: Métadonnées à réinjecter.
        quality: Qualité JPEG (95 par défaut).
        suffix: Suffixe ajouté au nom (si path_out = input/foo.jpg, sortie = output/foo_rectified.jpg).
    """
    path_out.parent.mkdir(parents=True, exist_ok=True)
    rgb = img_bgr[:, :, ::-1]
    pil = Image.fromarray(rgb)

    save_kwargs: dict[str, Any] = {}
    ext = path_out.suffix.lower()

    if ext in (".jpg", ".jpeg"):
        save_kwargs["quality"] = quality
        save_kwargs["subsampling"] = 0
        if meta.icc_profile:
            save_kwargs["icc_profile"] = meta.icc_profile
        if HAS_PIEXIF and meta.exif_bytes:
            try:
                exif_dict = piexif.load(meta.exif_bytes)
                exif_dict["0th"][piexif.ImageIFD.Orientation] = 1
                if "Exif" in exif_dict:
                    exif_dict["Exif"][piexif.ExifIFD.Orientation] = 1
                save_kwargs["exif"] = piexif.dump(exif_dict)
            except Exception as e:
                logger.warning("Exif réinjection échouée: %s", e)
    elif ext in (".png", ".tiff", ".tif"):
        if meta.icc_profile:
            save_kwargs["icc_profile"] = meta.icc_profile
        if ext in (".tiff", ".tif"):
            save_kwargs["compression"] = "tiff_lzw"

    pil.save(path_out, **save_kwargs)
    logger.info("Sauvegardé: %s", path_out)


def build_output_path(
    input_path: Path, output_dir: Path, suffix: str = "_rectified"
) -> Path:
    """Construit le chemin de sortie: output_dir / stem_suffix.ext."""
    return output_dir / f"{input_path.stem}{suffix}{input_path.suffix}"
