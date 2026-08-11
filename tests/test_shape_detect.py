"""Shape detection from the drawing's pixels.

The cost of being wrong is asymmetric. A missed curve is a flat price the PM can correct on
a row that is visibly wrong. A *false* curve inflates the price twice — arc length plus the
curved-work factor — and then demands a curve rise the PM has to invent. So these tests
care more about straight things staying straight than about catching every curve.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import shape_detect  # noqa: E402

pytestmark = pytest.mark.skipif(not shape_detect.AVAILABLE,
                                reason="OpenCV not installed (comes with easyocr)")


def _canvas(width=400, height=400):
    import numpy as np
    return np.full((height, width, 3), 255, dtype=np.uint8)


class TestDetection:
    def test_a_circle_is_read_as_a_ring_shelf(self):
        import cv2
        img = _canvas()
        cv2.circle(img, (200, 200), 120, (0, 0, 0), 3)
        found = shape_detect.detect(img, (0, 0, 400, 400))
        assert found and found["shape"] == "ring"

    def test_a_straight_panel_is_not_reported_as_curved(self):
        """The expensive false positive: a flat wall priced as curved joinery."""
        import cv2
        img = _canvas()
        cv2.rectangle(img, (60, 60), (340, 340), (0, 0, 0), 3)
        found = shape_detect.detect(img, (0, 0, 400, 400))
        assert found is None or found["shape"] != "curved"

    def test_a_bowed_line_is_read_as_curved(self):
        import cv2
        import numpy as np
        img = _canvas()
        pts = np.array([[[x, int(300 - 120 * np.sin(np.pi * (x - 60) / 280))]]
                        for x in range(60, 341, 4)], dtype=np.int32)
        cv2.polylines(img, [pts], False, (0, 0, 0), 3)
        found = shape_detect.detect(img, (0, 0, 400, 400))
        assert found and found["shape"] == "curved"

    def test_a_blank_area_yields_nothing(self):
        assert shape_detect.detect(_canvas(), (0, 0, 400, 400)) is None

    def test_a_box_too_small_to_judge_is_skipped(self):
        assert shape_detect.detect(_canvas(), (0, 0, 5, 5)) is None


class TestScaleHandling:
    def test_a_curve_without_a_scale_gets_no_invented_rise(self):
        """The rise decides what a curve costs; it must be measured, never guessed."""
        import cv2
        import numpy as np
        img = _canvas()
        pts = np.array([[[x, int(300 - 120 * np.sin(np.pi * (x - 60) / 280))]]
                        for x in range(60, 341, 4)], dtype=np.int32)
        cv2.polylines(img, [pts], False, (0, 0, 0), 3)
        found = shape_detect.detect(img, (0, 0, 400, 400), px_per_m=0)
        assert found["shape"] == "curved"
        assert "sagitta_m" not in found

    def test_a_scale_turns_pixels_into_metres(self):
        import cv2
        img = _canvas()
        cv2.circle(img, (200, 200), 100, (0, 0, 0), 3)
        found = shape_detect.detect(img, (0, 0, 400, 400), px_per_m=200.0)
        assert found["shape"] == "ring"
        assert found["outer_r_m"] == pytest.approx(0.5, abs=0.08)


class TestApplyToElements:
    def test_a_user_chosen_shape_is_never_overwritten(self):
        """A correction undone by a re-parse is worse than no detection at all."""
        import cv2
        img = _canvas()
        cv2.circle(img, (200, 200), 120, (0, 0, 0), 3)
        elements = [{"bbox_px": (0, 0, 400, 400), "shape": "wall_flat",
                     "shape_source": "user"}]
        shape_detect.apply_to_elements(img, elements)
        assert elements[0]["shape"] == "wall_flat"
        assert elements[0]["shape_source"] == "user"

    def test_an_undetected_element_is_marked_default_not_detected(self):
        elements = [{"bbox_px": (0, 0, 400, 400)}]
        shape_detect.apply_to_elements(_canvas(), elements)
        assert elements[0]["shape_source"] == "default"

    def test_a_detected_element_records_why(self):
        import cv2
        img = _canvas()
        cv2.circle(img, (200, 200), 120, (0, 0, 0), 3)
        elements = [{"bbox_px": (0, 0, 400, 400)}]
        assert shape_detect.apply_to_elements(img, elements) == 1
        assert elements[0]["shape_source"] == "detected"
        assert elements[0]["shape_reason"]
