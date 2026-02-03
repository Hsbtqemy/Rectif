"""Détection automatique des coins, warp perspective et améliorations."""

import logging
from typing import Optional

import cv2
import numpy as np
from numpy.typing import NDArray

from rectify_gui.utils_geom import four_point_transform, order_points

logger = logging.getLogger(__name__)

# Extensions supportées
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif"}


def auto_detect_corners(
    img: NDArray[np.uint8],
    min_area_ratio: float = 0.1,
    downscale: int = 800,
) -> tuple[NDArray[np.float32], bool]:
    """
    Détecte automatiquement les 4 coins du document.

    Args:
        img: Image BGR.
        min_area_ratio: Aire minimale du contour (ratio de l'image).
        downscale: Dimension max pour le traitement (vitesse).

    Returns:
        Tuple (4 points ordonnés, succès).
    """
    h, w = img.shape[:2]
    scale = min(downscale / max(h, w), 1.0)
    if scale < 1.0:
        small = cv2.resize(img, None, fx=scale, fy=scale)
    else:
        small = img

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 75, 200)
    edged = cv2.dilate(edged, None, iterations=2)

    contours, _ = cv2.findContours(
        edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area_ratio * small.shape[0] * small.shape[1]:
            continue
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        if len(approx) == 4:
            pts = approx.reshape(4, 2).astype(np.float32)
            if scale < 1.0:
                pts /= scale
            pts = order_points(pts)
            return pts, True

    # Échec: coins par défaut
    pts = np.array(
        [[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]],
        dtype=np.float32,
    )
    return pts, False


def warp_perspective(
    img: NDArray[np.uint8], pts: NDArray[np.float32]
) -> NDArray[np.uint8]:
    """
    Applique la transformation perspective.

    Args:
        img: Image source BGR.
        pts: 4 points ordonnés (tl, tr, br, bl).

    Returns:
        Image rectifiée.
    """
    dst, ordered = four_point_transform(img, pts)
    w = int(dst[2, 0]) + 1
    h = int(dst[2, 1]) + 1
    M = cv2.getPerspectiveTransform(ordered.astype(np.float32), dst)
    warped = cv2.warpPerspective(img, M, (w, h))
    return warped


def apply_denoise(
    img: NDArray[np.uint8], strength: float = 15.0
) -> NDArray[np.uint8]:
    """NLM denoising léger."""
    template = max(3, min(7, int(strength)))
    search = template * 2 + 1
    # Arguments positionnels pour compatibilité OpenCV 4.9–4.13
    # Signature: src, dst, h, hColor, templateWindowSize, searchWindowSize
    return cv2.fastNlMeansDenoisingColored(
        img, None, strength, strength, template, search
    )


def apply_clahe(
    img: NDArray[np.uint8], clip_limit: float = 3.0
) -> NDArray[np.uint8]:
    """CLAHE pour améliorer le contraste local (documents ternes)."""
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(
        clipLimit=clip_limit, tileGridSize=(8, 8)
    )
    l = clahe.apply(l)
    lab = cv2.merge([l, a, b])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def apply_sharpen(
    img: NDArray[np.uint8], amount: float = 1.8, sigma: float = 5.0
) -> NDArray[np.uint8]:
    """Unsharp mask : accentue les contours (sigma=rayon du flou à soustraire)."""
    blurred = cv2.GaussianBlur(img, (0, 0), sigma)
    # sharpened = img + (amount-1)*(img - blurred) = amount*img + (1-amount)*blurred
    sharpened = cv2.addWeighted(img, amount, blurred, 1 - amount, 0)
    return np.clip(sharpened, 0, 255).astype(np.uint8)


def clamp_size(
    img: NDArray[np.uint8],
    ref_max_dim: int,
    max_scale_factor: float = 1.25,
    min_scale_factor: float = 0.75,
) -> NDArray[np.uint8]:
    """
    Redimensionne si l'image dépasse les limites de taille.

    Args:
        img: Image à potentiellement redimensionner.
        ref_max_dim: Dimension max de référence (original).
        max_scale_factor: Si dim > ref * max_scale, downscale.
        min_scale_factor: Si dim < ref * min_scale, upscale.
    """
    h, w = img.shape[:2]
    current_max = max(h, w)
    max_allowed = int(ref_max_dim * max_scale_factor)
    min_allowed = int(ref_max_dim * min_scale_factor)

    if current_max > max_allowed:
        scale = max_allowed / current_max
        new_w = int(w * scale)
        new_h = int(h * scale)
        return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    if current_max < min_allowed:
        scale = min_allowed / current_max
        new_w = int(w * scale)
        new_h = int(h * scale)
        return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    return img


def full_pipeline(
    img: NDArray[np.uint8],
    pts: NDArray[np.float32],
    denoise: bool = False,
    denoise_strength: float = 10.0,
    clahe: bool = False,
    clahe_clip: float = 2.0,
    sharpen: bool = False,
    sharpen_amount: float = 1.8,
    clamp_enabled: bool = True,
    ref_max_dim: Optional[int] = None,
    max_scale_factor: float = 1.25,
    min_scale_factor: float = 0.75,
) -> NDArray[np.uint8]:
    """
    Pipeline complet: warp + post-traitement + clamp.

    Args:
        img: Image source.
        pts: 4 coins.
        denoise, clahe, sharpen: Options de post-traitement.
        clamp_enabled: Activer la limite de taille.
        ref_max_dim: Dimension max de référence (si None = max(h,w) de l'original).
    """
    result = warp_perspective(img, pts)
    ref = ref_max_dim or max(img.shape[:2])

    if denoise:
        result = apply_denoise(result, denoise_strength)
    if clahe:
        result = apply_clahe(result, clahe_clip)
    if sharpen:
        result = apply_sharpen(result, sharpen_amount)
    if clamp_enabled:
        result = clamp_size(
            result, ref,
            max_scale_factor=max_scale_factor,
            min_scale_factor=min_scale_factor,
        )
    return result


def get_display_image(
    img: NDArray[np.uint8], max_dim: int = 1200
) -> NDArray[np.uint8]:
    """Réduit l'image pour l'affichage (preview)."""
    h, w = img.shape[:2]
    if max(h, w) <= max_dim:
        return img
    scale = max_dim / max(h, w)
    new_w = int(w * scale)
    new_h = int(h * scale)
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
