# Types — Anytype API

Types define the schema for objects (like "Task", "Note", "Project", etc.).

## List Types
```bash
curl -s "http://127.0.0.1:31009/v1/spaces/<space_id>/types?limit=50" \
  -H "Authorization: Bearer <api_key>" \
  -H "Anytype-Version: 2025-11-08"
```

## Get Type
```bash
curl -s http://127.0.0.1:31009/v1/spaces/<space_id>/types/<type_id> \
  -H "Authorization: Bearer <api_key>" \
  -H "Anytype-Version: 2025-11-08"
```

## Create Type
```bash
curl -s -X POST http://127.0.0.1:31009/v1/spaces/<space_id>/types \
  -H "Authorization: Bearer <api_key>" \
  -H "Content-Type: application/json" \
  -H "Anytype-Version: 2025-11-08" \
  -d '{
    "name": "<type_name>",
    "layout": "<basic|profile|action|note>",
    "icon": "<emoji>",
    "properties": ["<property_id_1>", "<property_id_2>"]
  }'
```

### Layouts
- **basic**: General-purpose object (default)
- **profile**: Contact/person objects
- **action**: Task-like objects with done state
- **note**: Minimal, title-less objects

## Update Type
```bash
curl -s -X PATCH http://127.0.0.1:31009/v1/spaces/<space_id>/types/<type_id> \
  -H "Authorization: Bearer <api_key>" \
  -H "Content-Type: application/json" \
  -H "Anytype-Version: 2025-11-08" \
  -d '{
    "name": "<new_name>",
    "icon": "<new_emoji>"
  }'
```

## Delete Type
```bash
curl -s -X DELETE http://127.0.0.1:31009/v1/spaces/<space_id>/types/<type_id> \
  -H "Authorization: Bearer <api_key>" \
  -H "Anytype-Version: 2025-11-08"
```

## List Templates for a Type
```bash
curl -s http://127.0.0.1:31009/v1/spaces/<space_id>/types/<type_id>/templates \
  -H "Authorization: Bearer <api_key>" \
  -H "Anytype-Version: 2025-11-08"
```

## Get Template
```bash
curl -s http://127.0.0.1:31009/v1/spaces/<space_id>/types/<type_id>/templates/<template_id> \
  -H "Authorization: Bearer <api_key>" \
  -H "Anytype-Version: 2025-11-08"
```
