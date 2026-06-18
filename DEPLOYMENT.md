# Railway deployment

This repository deploys as two Railway services from the same GitHub source.
Each service must use its own root directory and config file.

Set the same `SESSION_SECRET` environment variable on both services. It must be
at least 32 random characters; changing it signs every user out.

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
