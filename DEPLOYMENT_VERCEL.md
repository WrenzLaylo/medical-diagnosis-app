# Vercel Deployment (Frontend + Django Backend)

## 1) Deploy backend as a separate Vercel project

1. In Vercel, click **New Project** and import this repo.
2. Set **Root Directory** to `backend`.
3. Vercel will use `backend/vercel.json`.
4. Add backend environment variables:
   - `DJANGO_SECRET_KEY`
   - `DJANGO_DEBUG=False`
   - `DJANGO_ALLOWED_HOSTS=.vercel.app`
   - `DJANGO_CORS_ALLOW_ALL=False`
   - `DJANGO_CORS_ALLOWED_ORIGINS=https://<frontend-project>.vercel.app`
   - `DJANGO_CSRF_TRUSTED_ORIGINS=https://<frontend-project>.vercel.app`
   - `DATABASE_URL` (Postgres; do not use SQLite in production)
   - `HF_TOKEN`
   - `WATSONX_API_KEY`
   - `WATSONX_PROJECT_ID`
   - `WATSONX_URL`
5. Deploy, then copy backend URL from **Project > Settings > Domains**.

## 2) Deploy frontend project

1. Create/import another Vercel project for the same repo (root stays repo root).
2. Add frontend env var:
   - `REACT_APP_API_BASE_URL=https://<backend-domain>/api`
3. Redeploy frontend.

## Exact API base URL format

Use:

`https://<your-backend-project>.vercel.app/api`

Example:

`https://medical-diagnosis-backend.vercel.app/api`
