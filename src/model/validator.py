"""
Input validation and out-of-distribution (OOD) screening filter.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple
import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError

@dataclass
class ValidationResult:
    is_valid: bool
    status: str
    rejection_reason: Optional[str] = None
    blur_score: Optional[float] = None
    foliage_ratio: Optional[float] = None

class InputValidator:
    def __init__(
        self,
        blur_threshold: float = 65.0,
        foliage_threshold: float = 0.05,
        enable_blur_check: bool = True,
        enable_ood_check: bool = True,
    ):
        self.blur_threshold = blur_threshold
        self.foliage_threshold = foliage_threshold
        self.enable_blur_check = enable_blur_check
        self.enable_ood_check = enable_ood_check
        self.analysis_dim = (256, 256)

    def validate_file(self, file_path: Path) -> Tuple[ValidationResult, Optional[Image.Image]]:
        if not file_path.exists() or file_path.stat().st_size == 0:
            return ValidationResult(False, "REJECTED_CORRUPTED", "Empty or non-existent file"), None

        try:
            with Image.open(file_path) as img:
                img.verify()
            pil_img = Image.open(file_path).convert("RGB")
        except (UnidentifiedImageError, OSError, ValueError) as err:
            return ValidationResult(False, "REJECTED_CORRUPTED", f"Unreadable byte stream: {err}"), None

        np_img = np.array(pil_img)
        h, w = np_img.shape[:2]
        if h < 64 or w < 64:
            return ValidationResult(False, "REJECTED_RESOLUTION", f"Resolution ({w}x{h}) < 64x64 minimum"), None

        # Standardize size for scale-invariant blur measurement
        standard_img = cv2.resize(np_img, self.analysis_dim, interpolation=cv2.INTER_AREA)

        # 1. Blur evaluation
        gray = cv2.cvtColor(standard_img, cv2.COLOR_RGB2GRAY)
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        if self.enable_blur_check and laplacian_var < self.blur_threshold:
            return ValidationResult(
                False,
                "REJECTED_BLURRED",
                f"Laplacian variance {laplacian_var:.1f} < threshold {self.blur_threshold}",
                blur_score=laplacian_var,
            ), None

        # 2. Plant chromaticity envelope (Green foliage + Dry necrotic brown + Sooty mould charcoal)
        hsv = cv2.cvtColor(standard_img, cv2.COLOR_RGB2HSV)
        mask_green = cv2.inRange(hsv, np.array([20, 25, 20]), np.array([95, 255, 255]))
        mask_brown = cv2.inRange(hsv, np.array([8, 30, 20]), np.array([24, 255, 200]))
        mask_sooty = cv2.inRange(hsv, np.array([0, 0, 10]), np.array([180, 120, 65]))

        plant_mask = cv2.bitwise_or(mask_green, cv2.bitwise_or(mask_brown, mask_sooty))
        foliage_ratio = float(np.count_nonzero(plant_mask) / (self.analysis_dim[0] * self.analysis_dim[1]))

        if self.enable_ood_check and foliage_ratio < self.foliage_threshold:
            return ValidationResult(
                False,
                "REJECTED_OOD_NON_LEAF",
                f"Plant tissue ratio {foliage_ratio:.3f} < threshold {self.foliage_threshold}",
                blur_score=laplacian_var,
                foliage_ratio=foliage_ratio,
            ), None

        return ValidationResult(
            True, "PASSED", blur_score=laplacian_var, foliage_ratio=foliage_ratio
        ), pil_img
    