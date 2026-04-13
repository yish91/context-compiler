# Auth Domain

Cross-cutting domain identified via: config_name, model_name, route_filename, route_path.

## Key Files
- `api/auth.py`
- `api/auth_routes.py`
- `web/src/auth/Login.tsx`

## Related Routes
- `/auth/login`
- `/auth/logout`
- `/auth/me`

## Related Models
- `AuthCredentials` (username, password) in `api/auth.py`
- `AuthToken` (token, user_id, expires_at) in `api/auth.py`

## Related Components
- `Login` (props: onSuccess) in `web/src/auth/Login.tsx`

## Related Config
- `AUTH_SECRET` (env) in `api/auth.py`
- `AUTH_TOKEN_EXPIRY` (env) in `api/auth.py`

## Also Inspect
If you change this domain, also inspect:
- `web/src/App.tsx`
- `web/src/config.ts`
