# Members — Anytype API

View members of a shared space.

## List Members
```bash
curl -s http://127.0.0.1:31009/v1/spaces/<space_id>/members \
  -H "Authorization: Bearer <api_key>" \
  -H "Anytype-Version: 2025-11-08"
```

## Get Member
```bash
curl -s http://127.0.0.1:31009/v1/spaces/<space_id>/members/<member_id> \
  -H "Authorization: Bearer <api_key>" \
  -H "Anytype-Version: 2025-11-08"
```

## Response Shape
```json
{
  "member": {
    "id": "...",
    "name": "Julian",
    "icon": "...",
    "role": "owner",
    "global_name": "..."
  }
}
```

## Roles
- **owner** — Full control of the space
- **writer** — Can create, edit, and delete objects
- **reader** — Read-only access
