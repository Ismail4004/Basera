"""Static file storage for production."""

from whitenoise.storage import CompressedManifestStaticFilesStorage


class ForgivingManifestStorage(CompressedManifestStaticFilesStorage):
    """Gzip/Brotli copies, plus a content hash in every file name (app.3f2a9c.css).

    The hash lets browsers keep each file for a year without asking again, so a
    repeat visit downloads almost nothing. `manifest_strict = False` makes a file
    that is missing from the manifest load under its plain name instead of
    raising an error (for example when tests run before `collectstatic`).
    """

    manifest_strict = False
