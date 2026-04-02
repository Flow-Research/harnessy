# Spaces — Anytype API

## List Spaces
```bash
curl -s http://127.0.0.1:31009/v1/spaces \
  -H "Authorization: Bearer <api_key>" \
  -H "Anytype-Version: 2025-11-08"
```

## Create Space
```bash
curl -s -X POST http://127.0.0.1:31009/v1/spaces \
  -H "Authorization: Bearer <api_key>" \
  -H "Content-Type: application/json" \
  -H "Anytype-Version: 2025-11-08" \
  -d '{
    "name": "<space_name>"
  }'
```

## Get Space
```bash
curl -s http://127.0.0.1:31009/v1/spaces/<space_id> \
  -H "Authorization: Bearer <api_key>" \
  -H "Anytype-Version: 2025-11-08"
```

## Update Space
```bash
curl -s -X PATCH http://127.0.0.1:31009/v1/spaces/<space_id> \
  -H "Authorization: Bearer <api_key>" \
  -H "Content-Type: application/json" \
  -H "Anytype-Version: 2025-11-08" \
  -d '{
    "name": "<new_name>"
  }'
```

## Response Shape
```json
{
  "space": {
    "id": "baf...",
    "name": "My Space",
    "icon": "...",
    "home_object_id": "...",
    "archive_object_id": "...",
    "profile_object_id": "...",
    "marketplace_workspace_id": "...",
    "created_date": "2025-01-01T00:00:00Z",
    "account_status": "active",
    "network_id": "..."
  }
}
```
