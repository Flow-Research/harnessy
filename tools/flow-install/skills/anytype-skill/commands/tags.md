# Tags — Anytype API

Tags are option values for `select` and `multi_select` property formats.

## List Tags
```bash
curl -s http://127.0.0.1:31009/v1/spaces/<space_id>/properties/<property_id>/tags \
  -H "Authorization: Bearer <api_key>" \
  -H "Anytype-Version: 2025-11-08"
```

## Get Tag
```bash
curl -s http://127.0.0.1:31009/v1/spaces/<space_id>/properties/<property_id>/tags/<tag_id> \
  -H "Authorization: Bearer <api_key>" \
  -H "Anytype-Version: 2025-11-08"
```

## Create Tag
```bash
curl -s -X POST http://127.0.0.1:31009/v1/spaces/<space_id>/properties/<property_id>/tags \
  -H "Authorization: Bearer <api_key>" \
  -H "Content-Type: application/json" \
  -H "Anytype-Version: 2025-11-08" \
  -d '{
    "name": "<tag_name>",
    "color": "<color>"
  }'
```

### Colors
Anytype supports a predefined set of tag colors. Common values: `grey`, `yellow`, `orange`, `red`, `pink`, `purple`, `blue`, `ice`, `teal`, `lime`.

## Update Tag
```bash
curl -s -X PATCH http://127.0.0.1:31009/v1/spaces/<space_id>/properties/<property_id>/tags/<tag_id> \
  -H "Authorization: Bearer <api_key>" \
  -H "Content-Type: application/json" \
  -H "Anytype-Version: 2025-11-08" \
  -d '{
    "name": "<new_name>",
    "color": "<new_color>"
  }'
```

## Delete Tag
```bash
curl -s -X DELETE http://127.0.0.1:31009/v1/spaces/<space_id>/properties/<property_id>/tags/<tag_id> \
  -H "Authorization: Bearer <api_key>" \
  -H "Anytype-Version: 2025-11-08"
```
