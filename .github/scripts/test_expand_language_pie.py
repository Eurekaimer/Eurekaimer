from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

SCRIPT_PATH = Path(__file__).with_name("expand_language_pie.py")
SPEC = importlib.util.spec_from_file_location("expand_language_pie", SCRIPT_PATH)
assert SPEC and SPEC.loader
SCRIPT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCRIPT)


class ExpandLanguagePieTest(unittest.TestCase):
    def test_rebuild_language_pie_replaces_other_with_all_named_languages(self) -> None:
        original = """\
<svg xmlns="http://www.w3.org/2000/svg">
  <g transform="translate(40, 520)">
    <text>other</text>
  </g>
</svg>
"""
        languages = [
            {"language": "Python", "color": "#3572A5", "contributions": 8},
            {"language": "Rust", "color": "#dea584", "contributions": 2},
        ]

        with tempfile.TemporaryDirectory() as temporary_directory:
            svg_path = Path(temporary_directory) / "profile.svg"
            svg_path.write_text(original, encoding="utf-8")
            SCRIPT.rebuild_language_pie(svg_path, languages)
            root = ET.parse(svg_path).getroot()

        labels = [
            element.text
            for element in root.iter(SCRIPT.svg_tag("text"))
            if element.text
        ]
        titles = [
            element.text
            for element in root.iter(SCRIPT.svg_tag("title"))
            if element.text
        ]
        self.assertEqual(labels, ["Python", "Rust"])
        self.assertEqual(titles, ["Python 8", "Rust 2"])
        self.assertNotIn("other", labels)

    def test_donut_path_supports_a_single_language(self) -> None:
        path = SCRIPT.donut_path(0, SCRIPT.math.tau)
        self.assertEqual(path.count("A117,117"), 2)
        self.assertEqual(path.count("A65,65"), 2)


if __name__ == "__main__":
    unittest.main()
