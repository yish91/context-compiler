# Database Models

Contains 7 data models.

## Key Files
- `api/auth.py` (2 models)
- `api/schema.py` (3 models)
- `web/src/App.tsx` (1 model)
- `web/src/auth/Login.tsx` (1 model)

## Models
- `AuthCredentials` (class) in `api/auth.py` - fields: username, password
- `AuthToken` (class) in `api/auth.py` - fields: token, user_id, expires_at
- `CreatePageRequest` (class) in `api/schema.py` - fields: title, content
- `User` (class) in `api/schema.py` - fields: id, username, email
- `WikiPage` (class) in `api/schema.py` - fields: id, title, content
- `AppProps` (interface) in `web/src/App.tsx` - fields: title
- `LoginProps` (interface) in `web/src/auth/Login.tsx` - fields: onSuccess
