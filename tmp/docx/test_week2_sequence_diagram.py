from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_week2_reports as reports


class SequenceDiagramReadabilityTest(unittest.TestCase):
    def test_note_band_is_separate_from_sequence_area(self):
        layout = reports.sequence_diagram_layout()
        event_bottom = max(event[0] for event in layout["events"])
        note_left, note_top, note_right, note_bottom = layout["note_box"]

        self.assertGreaterEqual(note_top - event_bottom, 90)
        self.assertLess(layout["lifeline_bottom"], note_top)
        self.assertGreater(note_right, note_left)
        self.assertLessEqual(note_bottom, layout["canvas"][1])

    def test_lanes_and_message_type_are_large_enough(self):
        layout = reports.sequence_diagram_layout()
        gaps = [right - left for left, right in zip(layout["xs"], layout["xs"][1:])]

        self.assertGreaterEqual(min(gaps), 390)
        self.assertGreaterEqual(layout["message_font_size"], 30)
        self.assertGreaterEqual(layout["note_font_size"], 28)

    def test_rendered_asset_has_expected_canvas(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "sequence.png"
            reports.build_sequence_diagram(output)
            with Image.open(output) as image:
                self.assertEqual(reports.sequence_diagram_layout()["canvas"], image.size)
                self.assertEqual("RGB", image.mode)


if __name__ == "__main__":
    unittest.main()
