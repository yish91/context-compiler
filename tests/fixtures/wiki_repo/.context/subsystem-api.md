# Api Subsystem

Contains: 5 files, 6 endpoints, 5 models.

## Key Files
- `api/server.py` (entry point)
- `api/auth.py` (models)
- `api/auth_routes.py` (routes)
- `api/routes.py` (routes)
- `api/schema.py` (models)

## Routes
- `POST /auth/login` - login
- `POST /auth/logout` - logout
- `GET /auth/me` - get_current_user
- `GET /health` - health_check
- `POST /pages` - create_page
- `GET /pages/{page_id}` - get_page

## Models
- `AuthCredentials` (username, password)
- `AuthToken` (token, user_id, expires_at)
- `CreatePageRequest` (title, content)
- `User` (id, username, email)
- `WikiPage` (id, title, content)

## Config
- `AUTH_SECRET` (env)
- `AUTH_TOKEN_EXPIRY` (env)
- `APP_NAME` (env)

## Also Inspect
If you change this area, also inspect:
- `web/src/config.ts`
