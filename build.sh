#!/usr/bin/env bash
# Build step for the host (Render runs this before starting the site).
# Stops at the first error so a broken build is never deployed.
set -o errexit

pip install -r requirements.txt

# Gather the CSS, JS and images into staticfiles/ for WhiteNoise to serve.
python manage.py collectstatic --noinput

# Create or update the database tables.
python manage.py migrate --noinput

# Add the regions and the 35 starter plants (and put back any missing photo files).
# Safe to run on every deploy: anything already there is left alone.
python manage.py seed_catalog
