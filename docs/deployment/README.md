# Deploying Basera (Render)

Basera is set up to go live on [Render](https://render.com) from `render.yaml`. This
guide is for the person doing the first deploy. Everything the code needs is already
in the repository: the steps below are only the things that need *your* accounts and
secrets.

## What was set up

| Need | How it is handled |
|---|---|
| Web server | `gunicorn` (started by `render.yaml`) |
| CSS, JS, images | `collectstatic` in `build.sh`, served by WhiteNoise |
| Database | Render PostgreSQL; the app reads its `DATABASE_URL` |
| Debug off | automatic on Render (`RENDER=true`), or `DEBUG=False` anywhere else |
| Secret key | Render generates one; the site refuses to start without one when debug is off |
| Site address | Render's address is added to `ALLOWED_HOSTS` and trusted origins automatically |
| HTTPS | redirect to https, secure cookies, HSTS (1 hour at first) |
| Starter plants and photos | `seed_catalog` runs on every deploy and puts missing photos back |
| Demo logins | none on the live site (`SEED_DEMO_ACCOUNTS=False`); the admin is made from variables |

## First deploy

1. **Merge `dev` into `main`** on GitHub (open a pull request from `dev` and merge it).
2. Sign in to Render with GitHub. Choose **New > Blueprint**, pick the `Basera`
   repository and the `main` branch. Render reads `render.yaml` and shows a database
   (`basera-db`) and a web service (`basera`).
3. Render asks for the variables marked `sync: false`. Fill in:
   - `ADMIN_EMAIL`: the email you will use to log in as site admin.
   - `ADMIN_PASSWORD`: a strong password (at least 8 characters, not common, not
     all numbers). It is stored hashed; nobody can read it back later.
   - `EMAIL_ADDRESS` and `EMAIL_APP_PASSWORD` (optional): the Gmail address and its
     16-character app password, so password-reset emails really go out. Without them
     the reset link is only printed in the service's log.
4. Press **Apply**. The first build takes a few minutes: it installs packages,
   collects static files, creates the tables and adds the 35 plants.
5. Open the address Render shows (`https://basera-xxxx.onrender.com`).

## Check it worked

- The home page opens and the catalogue shows 35 plants with photos.
- Sign up as a customer, create a grow profile, press **Find plants**.
- Log in with `ADMIN_EMAIL` / `ADMIN_PASSWORD` and see the admin landing page.
- A made-up address such as `/nope/` shows the butterfly 404 page, not a technical page.

## Good to know (free plan)

These come from Render's free plan, so check [render.com/pricing](https://render.com/pricing)
before relying on them:

- The web service **sleeps after about 15 minutes** without visitors. The first visit
  afterwards takes 30 to 60 seconds. Open the site a minute before a demo.
- The free database is **time-limited** (reported as 30 days). Create it close to
  the demo date. A paid database starts at a few dollars a month.
- The disk is wiped on restart. The 35 seeded photos come back on every deploy, but
  a photo a seller uploads later would be lost; add a persistent disk or cloud
  storage (S3, Cloudinary) before sellers can upload.
- `PYTHON_VERSION` in `render.yaml` is `3.13.9`. If Render says it does not have that
  version, change it to one it lists.

## Updating the live site

Push to `main`. Render rebuilds and redeploys by itself. `build.sh` is safe to run
every time: tables are only changed by new migrations and plants already in the
catalogue are left alone.

## Running the same setup on your own computer

To rehearse a live build locally (this is how it was tested), make an empty database,
then:

```bash
export DEBUG=False SECRET_KEY='<any long random text>' ALLOWED_HOSTS=127.0.0.1
export DATABASE_URL='postgres://basera_app:<password>@localhost:5433/<empty database>'
export SEED_DEMO_ACCOUNTS=False SERVE_MEDIA=True SECURE_SSL_REDIRECT=False
export ADMIN_EMAIL=you@example.com ADMIN_PASSWORD='<strong password>'
./build.sh
gunicorn basera_site.wsgi:application --bind 127.0.0.1:8100
```

`SECURE_SSL_REDIRECT=False` is only for trying it over plain http.

## Variables reference

`DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DATABASE_URL`,
`SERVE_MEDIA`, `SEED_DEMO_ACCOUNTS`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_NAME`,
`NURSERY_NAME`, `EMAIL_ADDRESS`, `EMAIL_APP_PASSWORD`, `SECURE_SSL_REDIRECT`,
`SECURE_HSTS_SECONDS`. Locally they live in `.env` (see `.env.example`).

## Left for later

- Raise `SECURE_HSTS_SECONDS` (for example to 31536000, one year) once the site is stable.
- Two optional Django security notes (`SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD`)
  are left off on purpose: preload is a permanent commitment for the whole domain.
