# Anytype Files

Use these endpoints for native Anytype file objects. They require the same
local base URL and API key as the rest of the Anytype skill.

## Upload File

Uploads a local file into a Space and returns a native Anytype file object ID.
Use multipart form data, not JSON.

```bash
curl -s -X POST "http://127.0.0.1:31009/v1/spaces/<space_id>/files" \
  -H "Authorization: Bearer <api_key>" \
  -H "Anytype-Version: 2025-11-08" \
  -F "file=@/path/to/file"
```

Expected response fields include:

- `object_id`: uploaded file object ID
- `name`: uploaded filename
- `media`: Anytype media kind
- `extension`: file extension
- `size_in_bytes`: uploaded file size

## Download File

```bash
curl -s "http://127.0.0.1:31009/v1/spaces/<space_id>/files/<file_id>" \
  -H "Authorization: Bearer <api_key>" \
  -H "Anytype-Version: 2025-11-08" \
  -o ./downloaded-file
```

For image files, the API also accepts an optional `width` query parameter.

## Delete File

```bash
curl -s -X DELETE "http://127.0.0.1:31009/v1/spaces/<space_id>/files/<file_id>?skip_bin=false" \
  -H "Authorization: Bearer <api_key>" \
  -H "Anytype-Version: 2025-11-08"
```

Set `skip_bin=true` only when you need to remove the object reference while
leaving the binary data untouched.
