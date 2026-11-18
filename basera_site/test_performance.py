"""Speed budgets (test-case section A19): image sizes, caching and non-blocking scripts.

These keep the live site quick on Render's small free plan: a page should not
need megabytes of images, repeat visits should reuse cached files, and nothing
from another website should stop the page from drawing.
"""

import re
import shutil
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from PIL import Image

from .test_deploy import run_django

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "accounts" / "static" / "accounts" / "img"
SEED = ROOT / "catalog" / "seed_images"


class ImageBudgetTests(SimpleTestCase):
    def test_pf01_every_plant_photo_is_at_most_720px_and_200kb(self):
        photos = sorted(SEED.glob("*.jpg"))
        self.assertEqual(len(photos), 35)
        for photo in photos:
            with self.subTest(photo=photo.name):
                self.assertLessEqual(photo.stat().st_size, 200 * 1024)
                self.assertLessEqual(max(Image.open(photo).size), 720)

    def test_pf02_all_plant_photos_together_stay_under_3mb(self):
        self.assertLess(sum(p.stat().st_size for p in SEED.glob("*.jpg")), 3 * 1024 * 1024)

    def test_pf03_the_home_page_hero_is_at_most_1920px_wide_and_250kb(self):
        hero = IMG / "botanical-hero.jpg"
        self.assertLessEqual(hero.stat().st_size, 250 * 1024)
        self.assertLessEqual(Image.open(hero).width, 1920)

    def test_pf04_the_login_background_is_a_jpeg_under_150kb(self):
        background = IMG / "background.jpg"
        self.assertLessEqual(background.stat().st_size, 150 * 1024)
        self.assertFalse((IMG / "background.png").exists(), "the 1 MB PNG should not ship")
        self.assertIn("background.jpg", (ROOT / "accounts/static/accounts/css/basera.css").read_text())

    def test_pf05_no_image_in_the_static_folder_is_over_400kb(self):
        for image in IMG.iterdir():
            with self.subTest(image=image.name):
                self.assertLessEqual(image.stat().st_size, 400 * 1024)


class NonBlockingScriptTests(SimpleTestCase):
    def test_pf06_scripts_from_other_websites_never_block_the_page(self):
        for template in ("accounts/templates/accounts/site_base.html", "accounts/templates/accounts/base.html"):
            text = (ROOT / template).read_text()
            for tag in re.findall(r"<script[^>]+src=\"https?://[^>]*>", text):
                with self.subTest(template=template, tag=tag):
                    self.assertTrue("defer" in tag or "async" in tag, tag)


class CachingTests(SimpleTestCase):
    def test_pf07_production_uses_hashed_static_file_names_that_never_error_when_missing(self):
        done = run_django("shell", "-c",
                          "from django.conf import settings as s; from django.utils.module_loading import import_string\n"
                          "cls = import_string(s.STORAGES['staticfiles']['BACKEND'])\n"
                          "print(cls.__name__, cls.manifest_strict)",
                          DEBUG="False", ALLOWED_HOSTS="x.example.com", SECRET_KEY="k" * 60)
        self.assertIn("ForgivingManifestStorage False", done.stdout, done.stdout + done.stderr)

    def test_pf08_seeded_photos_are_served_with_a_week_of_caching(self):
        folder = Path(settings.MEDIA_ROOT) / "_perf_test"
        created_media = not Path(settings.MEDIA_ROOT).exists()
        folder.mkdir(parents=True, exist_ok=True)
        try:
            (folder / "x.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 64)
            done = run_django(
                "shell", "-c",
                "from wsgiref.util import setup_testing_defaults\n"
                "import basera_site.wsgi as w\n"
                "env = {'PATH_INFO': '/media/_perf_test/x.jpg', 'REQUEST_METHOD': 'GET', 'HTTP_HOST': 'x.example.com',\n"
                "       'wsgi.url_scheme': 'https', 'HTTP_X_FORWARDED_PROTO': 'https'}\n"
                "setup_testing_defaults(env)\n"
                "seen = {}\n"
                "def start(status, headers, exc=None): seen['status'] = status; seen['headers'] = dict(headers)\n"
                "b''.join(w.application(env, start))\n"
                "print(seen['status'], seen['headers'].get('Cache-Control'), type(w.application).__name__)",
                DEBUG="False", SERVE_MEDIA="True", ALLOWED_HOSTS="x.example.com", SECRET_KEY="k" * 60,
                MEDIA_ROOT=str(settings.MEDIA_ROOT))
        finally:
            shutil.rmtree(folder, ignore_errors=True)
            if created_media:
                shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        self.assertIn("200 OK", done.stdout, done.stdout + done.stderr)
        self.assertIn("max-age=604800", done.stdout)
        self.assertIn("WhiteNoise", done.stdout)

    def test_pf09_the_server_handles_several_requests_at_once(self):
        text = (ROOT / "render.yaml").read_text()
        self.assertRegex(text, r"--workers 2 --threads 4")
