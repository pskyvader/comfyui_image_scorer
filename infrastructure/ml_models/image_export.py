"""Batch tensor export for node outputs."""

from typing import TYPE_CHECKING

import numpy as np
import torch
from torch import Tensor

if TYPE_CHECKING:
    from PIL.Image import Image


def export_image_batch(pil_images: list["Image"]) -> Tensor:
    if not pil_images:
        return torch.zeros((1, 1, 1, 3), dtype=torch.float32)  # type: ignore[reportPrivateImportUsage]
    tensors: list[Tensor] = []
    for img in pil_images:
        np_img = np.array(img.convert("RGB"))
        np_img = np_img.astype(np.float32) / 255.0
        t = torch.from_numpy(np_img).unsqueeze(0)  # type: ignore[reportPrivateImportUsage]
        tensors.append(t)
    return torch.cat(tensors, dim=0)  # type: ignore[reportPrivateImportUsage]
