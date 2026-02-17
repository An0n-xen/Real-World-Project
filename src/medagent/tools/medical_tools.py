"""Built-in placeholder medical tools for MedAgent-Pro.

These are **mock** implementations that generate placeholder outputs.
Replace them with real models (MedSAM, Cellpose, etc.) for production use.

All tools follow the standard signature::

    tool_function(image_path: str, save_dir: str, save_name: str)
"""

from __future__ import annotations

import os

import numpy as np
from PIL import Image

from medagent.logger import get_logger

logger = get_logger(__name__)


def segment_optic_disc(image_path: str, save_dir: str, save_name: str) -> str:
    """Segment the optic disc from a fundus image.

    **Placeholder**: generates a circular mask centered in the image.
    Replace with a real segmentation model (e.g., MedSAM) for production.

    Args:
        image_path: Path to the input fundus image.
        save_dir: Directory to save the segmentation mask.
        save_name: Filename for the output mask image.

    Returns:
        Path to the saved mask image.
    """
    logger.info("Segmenting optic disc (placeholder)  input=%s", image_path)
    os.makedirs(save_dir, exist_ok=True)
    output_path = os.path.join(save_dir, save_name)

    try:
        img = Image.open(image_path)
        w, h = img.size
    except Exception:
        logger.warning("Could not open image, using default size 512x512")
        w, h = 512, 512

    # Generate a circular mask (placeholder for optic disc)
    mask = np.zeros((h, w), dtype=np.uint8)
    cy, cx = h // 2, w // 2
    radius = min(h, w) // 6  # disc is ~1/6 of image size
    Y, X = np.ogrid[:h, :w]
    dist = (X - cx) ** 2 + (Y - cy) ** 2
    mask[dist <= radius**2] = 255

    Image.fromarray(mask).save(output_path)
    logger.info("Optic disc mask saved → %s", output_path)
    return output_path


def segment_optic_cup(image_path: str, save_dir: str, save_name: str) -> str:
    """Segment the optic cup from a fundus image.

    **Placeholder**: generates a smaller circular mask inside the disc region.
    Replace with a real segmentation model for production.

    Args:
        image_path: Path to the input fundus image.
        save_dir: Directory to save the segmentation mask.
        save_name: Filename for the output mask image.

    Returns:
        Path to the saved mask image.
    """
    logger.info("Segmenting optic cup (placeholder)  input=%s", image_path)
    os.makedirs(save_dir, exist_ok=True)
    output_path = os.path.join(save_dir, save_name)

    try:
        img = Image.open(image_path)
        w, h = img.size
    except Exception:
        logger.warning("Could not open image, using default size 512x512")
        w, h = 512, 512

    # Generate a smaller circular mask (placeholder for optic cup)
    mask = np.zeros((h, w), dtype=np.uint8)
    cy, cx = h // 2, w // 2
    radius = min(h, w) // 10  # cup is smaller than disc
    Y, X = np.ogrid[:h, :w]
    dist = (X - cx) ** 2 + (Y - cy) ** 2
    mask[dist <= radius**2] = 255

    Image.fromarray(mask).save(output_path)
    logger.info("Optic cup mask saved → %s", output_path)
    return output_path
