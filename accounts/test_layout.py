"""One-screen layout of the log in, sign-up and password pages (test-case section A20).

The pixel measurements were taken in a browser (cases M-45 to M-47); these tests
stop the CSS rules that make it work from being removed by accident.
"""

import re
from pathlib import Path

from django.test import SimpleTestCase

CSS = (Path(__file__).resolve().parent / "static" / "accounts" / "css" / "basera.css").read_text()


class OneScreenLayoutTests(SimpleTestCase):
    def test_ly01_the_auth_pages_have_no_extra_scroll_room(self):
        self.assertRegex(CSS, r"--basera-scroll-room:\s*0px")

    def test_ly02_the_page_height_follows_the_visible_screen_including_phone_bars(self):
        self.assertIn("calc(100dvh + var(--basera-scroll-room))", CSS)

    def test_ly03_short_desktop_screens_get_tighter_spacing_at_three_heights(self):
        for height in (860, 740, 680):
            self.assertRegex(CSS, rf"@media \(min-width: 992px\) and \(max-height: {height}px\)")

    def test_ly04_fields_and_buttons_stay_44px_tall_in_the_compact_layouts(self):
        compact = CSS.split("Short desktop screens")[1].split("Accessibility: respect")[0]
        self.assertNotRegex(compact, r"min-height:\s*(?:[0-3]\d|4[0-3])px")  # never below 44
        self.assertEqual(re.findall(r"\.basera-input-wrap[^{]*\{[^}]*height", compact), [])

    def test_ly05_the_login_background_file_the_css_names_exists(self):
        name = re.search(r'url\("\.\./img/(background\.[a-z]+)"\)', CSS).group(1)
        self.assertTrue((Path(__file__).resolve().parent / "static" / "accounts" / "img" / name).exists())
