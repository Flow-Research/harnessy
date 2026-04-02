# Objects — Anytype API

Objects are the core content unit in Anytype (pages, notes, tasks, bookmarks, etc.).

## List Objects
```bash
curl -s "http://127.0.0.1:31009/v1/spaces/<space_id>/objects?limit=25&offset=0" \
  -H "Authorization: Bearer <api_key>" \
  -H "Anytype-Version: 2025-11-08"
```

## Get Object
```bash
curl -s http://127.0.0.1:31009/v1/spaces/<space_id>/objects/<object_id> \
  -H "Authorization: Bearer <api_key>" \
  -H "Anytype-Version: 2025-11-08"
```

## Create Object
```bash
curl -s -X POST http://127.0.0.1:31009/v1/spaces/<space_id>/objects \
  -H "Authorization: Bearer <api_key>" \
  -H "Content-Type: application/json" \
  -H "Anytype-Version: 2025-11-08" \
  -d '{
    "name": "<object_name>",
    "type_key": "<type_key>",
    "icon": "<emoji>",
    "body": "<markdown_content>",
    "description": "<short_description>",
    "properties": {
      "<property_key>": "<value>"
    }
  }'
```

### Body Format
The `body` field accepts Markdown. Anytype converts it to its internal block structure.

### Type Keys
Common built-in type keys: `ot-page`, `ot-note`, `ot-task`, `ot-bookmark`, `ot-collection`, `ot-set`.
Custom types use their unique key from the Types API.

## Update Object
```bash
curl -s -X PATCH http://127.0.0.1:31009/v1/spaces/<space_id>/objects/<object_id> \
  -H "Authorization: Bearer <api_key>" \
  -H "Content-Type: application/json" \
  -H "Anytype-Version: 2025-11-08" \
  -d '{
    "name": "<new_name>",
    "body": "<new_markdown_content>",
    "properties": {
      "<property_key>": "<new_value>"
    }
  }'
```
Only include fields you want to change; omitted fields are left unchanged.

## Delete Object
```bash
curl -s -X DELETE http://127.0.0.1:31009/v1/spaces/<space_id>/objects/<object_id> \
  -H "Authorization: Bearer <api_key>" \
  -H "Anytype-Version: 2025-11-08"
```

## Response Shape
```json
{
  "object": {
    "id": "baf...",
    "name": "My Page",
    "type": "ot-page",
    "icon": "",
    "body": "# Heading\nContent here...",
    "description": "",
    "snippet": "first few lines...",
    "layout": "basic",
    "space_id": "baf...",
    "properties": { ... },
    "created_date": "2025-01-01T00:00:00Z",
    "last_modified_date": "2025-01-02T00:00:00Z"
  }
}
```

## Property Value Formats
- **text**: `"string value"`
- **number**: `123` or `45.6`
- **date**: `"2025-04-01T00:00:00Z"`
- **checkbox**: `true` or `false`
- **select**: `"<tag_id>"`
- **multi_select**: `["<tag_id_1>", "<tag_id_2>"]`
- **url**: `"https://example.com"`
- **email**: `"user@example.com"`
- **phone**: `"+1234567890"`
- **objects**: `["<object_id_1>", "<object_id_2>"]` (relations to other objects)
- **files**: `["<file_object_id>"]`
