"""Utilitaires géométriques pour la correction de perspective."""

import numpy as np
from numpy.typing import NDArray


def order_points(pts: NDArray[np.float32]) -> NDArray[np.float32]:
    """
    Ordonne les 4 points dans l'ordre: top-left, top-right, bottom-right, bottom-left.

    Args:
        pts: Tableau de 4 points (4, 2).

    Returns:
        Points ordonnés (4, 2).
    """
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]  # top-left: somme min
    rect[2] = pts[np.argmax(s)]  # bottom-right: somme max
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # top-right: diff min
    rect[3] = pts[np.argmax(diff)]  # bottom-left: diff max
    return rect


def four_point_transform(
    image: NDArray, pts: NDArray[np.float32]
) -> tuple[NDArray, NDArray[np.float32]]:
    """
    Calcule la matrice de transformation perspective et les dimensions de sortie.

    Args:
        image: Image source (H, W, C).
        pts: 4 points ordonnés (tl, tr, br, bl).

    Returns:
        Tuple (image warpee, pts ordonnés).
    """
    pts = order_points(pts)
    (tl, tr, br, bl) = pts

    width_a = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    width_b = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    max_width = max(int(width_a), int(width_b))

    height_a = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    height_b = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    max_height = max(int(height_a), int(height_b))

    dst = np.array(
        [
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1],
        ],
        dtype=np.float32,
    )

    return dst, pts


def pts_to_screen(
    pts: NDArray[np.float32], scale: float, offset_x: float, offset_y: float
) -> NDArray[np.float32]:
    """Convertit les points image en coordonnées écran (zoom + pan)."""
    result = pts.copy()
    result[:, 0] = result[:, 0] * scale + offset_x
    result[:, 1] = result[:, 1] * scale + offset_y
    return result


def screen_to_pts(
    screen_pts: NDArray[np.float32], scale: float, offset_x: float, offset_y: float
) -> NDArray[np.float32]:
    """Convertit les coordonnées écran en points image."""
    result = screen_pts.copy()
    result[:, 0] = (result[:, 0] - offset_x) / scale
    result[:, 1] = (result[:, 1] - offset_y) / scale
    return result
