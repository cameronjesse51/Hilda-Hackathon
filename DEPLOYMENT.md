# Railway deployment

This repository deploys as two Railway services from the same GitHub source.
Each service must use its own root directory and config file.

Set the same `SESSION_SECRET` environment variable on both services. It must be
at least 32 random characters; changing it signs every user out.

Set `API_INTERNAL_URL` on the web service to the FastAPI service's public or
Railway private URL. The OTP service uses it to resolve the verified phone to a
UUID profile and request the signed session.

The API service also requires `SUPABASE_SERVICE_ROLE_KEY`; profile identity
resolution runs server-side and must not use the browser-facing anon key.

## Optional developer login

To test without sending an OTP, set these variables on the API service:

```text
ENABLE_DEV_AUTH=true
DEV_AUTH_KEY=<at least 24 random characters>
DEV_AUTH_PHONE=<dedicated test phone in E.164 format>
```

Set `VITE_ENABLE_DEV_AUTH=true` on the web service and redeploy it. The developer
enters `DEV_AUTH_KEY` in the login UI; the key must never be placed in a `VITE_*`
variable because Vite values are public. Keep `ENABLE_DEV_AUTH=false` in public
production when the bypass is not actively needed.

## Web service

- Root Directory: `/`
- Config File: `/railway.json`
- Healthcheck: `/api/health`

The root config builds the Vite application and starts `server.js`, which serves
the static build and the temporary Express endpoints.

## API service

- Root Directory: `/backend`
- Config File: `/backend/railway.json`
- Healthcheck: `/api/health`

The backend config installs Python dependencies from `requirements.txt` and
starts FastAPI with Uvicorn.

After changing either service setting, deploy the latest commit and verify:

```text
https://<web-domain>/api/health
https://<api-domain>/api/health
```

The web response is `{"status":"ok"}`. The API response is
`{"status":"ok","service":"api"}`.
