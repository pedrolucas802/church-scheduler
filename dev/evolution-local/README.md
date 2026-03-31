# Evolution Local

This folder gives you a quick local Evolution API setup for development and testing.

It is intentionally lightweight:
- no PostgreSQL
- no Redis
- local in-memory cache enabled
- suitable for local tests and QR-based Baileys instances

## 1. Start Evolution locally

```bash
cd /Users/patriciarego/Desktop/church-scheduler/dev/evolution-local
cp .env.example .env
docker compose up -d
docker compose logs -f evolution-api
```

After startup, Evolution should be reachable at:

```text
http://localhost:8080
```

## 2. Create a local instance (quickest path)

Use a Baileys instance first if you want to validate the checklist -> WhatsApp flow without setting up Meta Cloud API yet.

```bash
curl --request POST \
  --url http://localhost:8080/instance/create \
  --header 'Content-Type: application/json' \
  --header 'apikey: change-me-now' \
  --data '{
    "instanceName": "church-scheduler",
    "integration": "WHATSAPP-BAILEYS",
    "qrcode": true
  }'
```

This should create the instance and return an `instanceName`. Some setups also return a `hash.apikey`.

## 3. Open the QR code

Generate the QR/pairing code:

```bash
curl --request GET \
  --url http://localhost:8080/instance/connect/church-scheduler \
  --header 'apikey: change-me-now'
```

Check connection state:

```bash
curl --request GET \
  --url http://localhost:8080/instance/connectionState/church-scheduler \
  --header 'apikey: change-me-now'
```

List instances and confirm the instance-specific `apikey` if you want to use it:

```bash
curl --request GET \
  --url http://localhost:8080/instance/fetchInstances \
  --header 'apikey: change-me-now'
```

If you prefer, you can also open the docs/UI at:

```text
http://localhost:8080
```

## 4. Point this app to your local Evolution server

Update the main project env file used by your Streamlit app:

```env
EVOLUTION_API_BASE_URL=http://host.docker.internal:8080
EVOLUTION_API_INSTANCE=church-scheduler
EVOLUTION_API_KEY=change-me-now
CHECKLIST_CONFIRM_WHATSAPP_NUMBER=5585XXXXXXXXX
```

Notes:
- `host.docker.internal` is the right value when your Streamlit app is running inside Docker on macOS and Evolution is exposed on the host at `localhost:8080`.
- `CHECKLIST_CONFIRM_WHATSAPP_NUMBER` should be the WhatsApp number that receives the checklist confirmation, digits only with country code.

Then rebuild the app container:

```bash
cd /Users/patriciarego/Desktop/church-scheduler
docker compose --env-file .prod-local.env -f docker-compose.local-prod.yml up -d --build app
```

## 5. Later on VPS

For production, prefer this architecture:
- Evolution API in Docker
- PostgreSQL enabled
- Redis enabled
- HTTPS public domain
- reverse proxy (Nginx / Traefik / Caddy)

Recommended production env direction:

```env
SERVER_TYPE=https
SERVER_PORT=8080
SERVER_URL=https://evolution.yourdomain.com
AUTHENTICATION_API_KEY=your-strong-global-api-key

DATABASE_ENABLED=true
DATABASE_PROVIDER=postgresql
DATABASE_CONNECTION_URI=postgresql://<DB_USER>:<DB_PASSWORD>@postgres:5432/evolution?schema=public

CACHE_REDIS_ENABLED=true
CACHE_REDIS_URI=redis://redis:6379/6
CACHE_LOCAL_ENABLED=false
```

For your app on the VPS, the corresponding values would look like:

```env
EVOLUTION_API_BASE_URL=https://evolution.yourdomain.com
EVOLUTION_API_INSTANCE=church-scheduler
EVOLUTION_API_KEY=your-strong-global-api-key
CHECKLIST_CONFIRM_WHATSAPP_NUMBER=5585XXXXXXXXX
```

## 6. If you want official WhatsApp Cloud API later

That is a separate step from "running Evolution". You will still need:
- Meta Business account approved
- permanent token
- WhatsApp Number ID
- WhatsApp Business ID

Then create the Evolution instance with:

```json
{
  "instanceName": "church-scheduler",
  "token": "META_PERMANENT_TOKEN",
  "number": "WHATSAPP_NUMBER_ID",
  "businessId": "WHATSAPP_BUSINESS_ID",
  "qrcode": false,
  "integration": "WHATSAPP-BUSINESS"
}
```

That mode is best for the VPS phase, not the very first local smoke test.
