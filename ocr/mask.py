import numpy as np
import pymupdf

class Mask:
    def __init__(self, page: pymupdf.Page):
        mask_dimensions = (round(page.rect.width), round(page.rect.height))
        self.mask = np.zeros(mask_dimensions)

    def _submask(self, rect: pymupdf.Rect) -> np.ndarray:
        return self.mask[round(rect.x0):round(rect.x1) + 1, round(rect.y0):round(rect.y1) + 1]

    def add_rect(self, rect: pymupdf.Rect):
        self._submask(rect).fill(1)

    def remove_rect(self, rect: pymupdf.Rect):
        self._submask(rect).fill(0)

    def intersects(self, rect: pymupdf.Rect) -> bool:
        return np.any(self._submask(rect))

    def coverage_ratio(self, rect: pymupdf.Rect) -> float:
        submask = self._submask(rect)
        return np.sum(submask) / np.size(submask)
