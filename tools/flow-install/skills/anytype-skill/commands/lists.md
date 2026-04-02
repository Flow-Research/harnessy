# Lists — Anytype API

Lists are sets (query-based) and collections (manual) that organize objects with views.

## List Views
Get available views for a list (set or collection).

```bash
curl -s http://127.0.0.1:31009/v1/spaces/<space_id>/lists/<list_id>/views \
  -H "Authorization: Bearer <api_key>" \
  -H "Anytype-Version: 2025-11-08"
```

## Get Objects in a View
```bash
curl -s "http://127.0.0.1:31009/v1/spaces/<space_id>/lists/<list_id>/views/<view_id>/objects?limit=25" \
  -H "Authorization: Bearer <api_key>" \
  -H "Anytype-Version: 2025-11-08"
```

## Add Objects to a List
```bash
curl -s -X POST http://127.0.0.1:31009/v1/spaces/<space_id>/lists/<list_id>/objects \
  -H "Authorization: Bearer <api_key>" \
  -H "Content-Type: application/json" \
  -H "Anytype-Version: 2025-11-08" \
  -d '{
    "object_ids": ["<object_id_1>", "<object_id_2>"]
  }'
```

## Remove Object from a List
```bash
curl -s -X DELETE http://127.0.0.1:31009/v1/spaces/<space_id>/lists/<list_id>/objects/<object_id> \
  -H "Authorization: Bearer <api_key>" \
  -H "Anytype-Version: 2025-11-08"
```

## Notes
- **Sets** are query-based: objects appear automatically based on type/filter criteria. You can still manually add/remove.
- **Collections** are manual: you explicitly add objects.
- Each list can have multiple **views** (grid, list, gallery, kanban) with different sorts/filters.
