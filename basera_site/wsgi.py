"""
WSGI config for basera_site project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'basera_site.settings')

application = get_wsgi_application()

# Plant photos that already exist when the server starts (the 35 seeded ones) are
# served straight from memory-mapped files with caching headers, like the CSS, instead
# of going through Django one request at a time. Anything added later still falls
# through to Django's /media/ route (see basera_site/urls.py).
from django.conf import settings  # noqa: E402

if settings.SERVE_MEDIA and not settings.DEBUG and os.path.isdir(settings.MEDIA_ROOT):
    from whitenoise import WhiteNoise  # noqa: E402

    application = WhiteNoise(application, max_age=60 * 60 * 24 * 7)
    application.add_files(str(settings.MEDIA_ROOT), prefix=settings.MEDIA_URL)
