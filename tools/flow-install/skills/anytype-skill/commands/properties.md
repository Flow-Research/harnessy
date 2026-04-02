# Properties — Anytype API

Properties are metadata fields on objects (formerly called "relations").

## List Properties
```bash
curl -s "http://127.0.0.1:31009/v1/spaces/<space_id>/properties?limit=50" \
  -H "Authorization: Bearer <api_key>" \
  -H "Anytype-Version: 2025-11-08"
```

## Get Property
```bash
curl -s http://127.0.0.1:31009/v1/spaces/<space_id>/properties/<property_id> \
  -H "Authorization: Bearer <api_key>" \
  -H "Anytype-Version: 2025-11-08"
```

## Create Property
```bash
curl -s -X POST http://127.0.0.1:31009/v1/spaces/<space_id>/properties \
  -H "Authorization: Bearer <api_key>" \
  -H "Content-Type: application/json" \
  -H "Anytype-Version: 2025-11-08" \
  -d '{
    "name": "<property_name>",
    "format": "<format>"
  }'
```

### Formats
- `text` — Free text
- `number` — Numeric value
- `select` — Single select (uses tags)
- `multi_select` — Multiple select (uses tags)
- `date` — Date/datetime
- `files` — File attachments
- `checkbox` — Boolean
- `url` — URL
- `email` — Email address
- `phone` — Phone number
- `objects` — Relations to other objects

## Update Property
```bash
curl -s -X PATCH http://127.0.0.1:31009/v1/spaces/<space_id>/properties/<property_id> \
  -H "Authorization: Bearer <api_key>" \
  -H "Content-Type: application/json" \
  -H "Anytype-Version: 2025-11-08" \
  -d '{
    "name": "<new_name>"
  }'
```

## Delete Property
```bash
curl -s -X DELETE http://127.0.0.1:31009/v1/spaces/<space_id>/properties/<property_id> \
  -H "Authorization: Bearer <api_key>" \
  -H "Anytype-Version: 2025-11-08"
```
