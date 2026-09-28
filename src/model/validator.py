"""
Input validation & out-of-distribution (OOD) filter.
Flags corrupt files, blurred images, and non-foliage inputs.
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
    vegetation_index: Optional[float] = None

class InputValidator:
    def __init__(self, blur_threshold: float = 80.0, vegetation_threshold: float = 0.08):
        self.blur_threshold = blur_threshold
        self.vegetation_threshold = vegetation_threshold

    def validate_file(self, file_path: Path) -> Tuple[ValidationResult, Optional[Image.Image]]:
        if not file_path.exists() or file_path.stat().st_size == 0:
            return ValidationResult(False, "REJECTED_CORRUPTED", "Empty or missing file"), None

        try:
            with Image.open(file_path) as img:
                img.verify()
            pil_img = Image.open(file_path).convert("RGB")
        except (UnidentifiedImageError, OSError, ValueError) as err:
            return ValidationResult(False, "REJECTED_CORRUPTED", f"Unreadable image: {err}"), None

        np_img = np.array(pil_img)
        h, w = np_img.shape[:2]
        if h < 64 or w < 64:
            return ValidationResult(False, "REJECTED_RESOLUTION", f"Resolution {w}x{h} too small"), None

        # Blur check via Laplacian variance
        gray = cv2.cvtColor(np_img, cv2.COLOR_RGB2GRAY)
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if laplacian_var < self.blur_threshold:
            return ValidationResult(
                False, "REJECTED_BLURRED", f"Laplacian variance {laplacian_var:.1f} < {self.blur_threshold}", blur_score=laplacian_var
            ), None

        # OOD Non-leaf check via foliage chromaticity (HSV)
        hsv = cv2.cvtColor(np_img, cv2.COLOR_RGB2HSV)
        lower_foliage = np.array([15, 30, 20])
        upper_foliage = np.array([95, 255, 255])
        foliage_mask = cv2.inRange(hsv, lower_foliage, upper_foliage)
        foliage_ratio = float(np.count_nonzero(foliage_mask) / (h * w))

        if foliage_ratio < self.vegetation_threshold:
            return ValidationResult(
                False,
                "REJECTED_OOD_NON_LEAF",
                f"Foliage ratio {foliage_ratio:.3f} < {self.vegetation_threshold}",
                blur_score=laplacian_var,
                vegetation_index=foliage_ratio,
            ), None

        return ValidationResult(True, "PASSED", blur_score=laplacian_var, vegetation_index=foliage_ratio), pil_img