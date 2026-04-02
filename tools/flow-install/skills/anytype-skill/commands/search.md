# Search — Anytype API

## Global Search
Search across all spaces.

```bash
curl -s -X POST http://127.0.0.1:31009/v1/search \
  -H "Authorization: Bearer <api_key>" \
  -H "Content-Type: application/json" \
  -H "Anytype-Version: 2025-11-08" \
  -d '{
    "query": "<search_term>",
    "sort": {"key": "last_modified_date", "direction": "desc"},
    "limit": 25,
    "offset": 0
  }'
```

## Space-Scoped Search
Search within a specific space.

```bash
curl -s -X POST http://127.0.0.1:31009/v1/spaces/<space_id>/search \
  -H "Authorization: Bearer <api_key>" \
  -H "Content-Type: application/json" \
  -H "Anytype-Version: 2025-11-08" \
  -d '{
    "query": "<search_term>",
    "types": ["<type_id>"],
    "sort": {"key": "last_modified_date", "direction": "desc"},
    "limit": 25,
    "offset": 0
  }'
```

## Filter Expressions
Use `filter` for structured queries with nested AND/OR conditions:

```json
{
  "query": "",
  "filter": {
    "and": [
      {"property": "type", "condition": "eq", "value": "<type_id>"},
      {"property": "name", "condition": "contains", "value": "meeting"}
    ]
  }
}
```

### Available Conditions
`eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `contains`, `ncontains`, `in`, `nin`, `all`, `empty`, `nempty`

### Sort Options
- **key**: Any property key (e.g., `name`, `last_modified_date`, `created_date`)
- **direction**: `asc`, `desc`, `custom`

### Pagination
- `limit`: Max results (default 100)
- `offset`: Skip N results
