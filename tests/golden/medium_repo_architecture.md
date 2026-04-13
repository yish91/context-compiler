# Architecture

## Entry points
- `api/server.py` — bootstrap [python-generic]
- `svc/main.go` — bootstrap [go-generic]

## Module dependency edges
- `web/src/App.tsx` → web/src/api.ts, web/src/components/Footer.tsx, web/src/components/Header.tsx

## Central files
- `web/src/api.ts` (in=1, out=0)
- `web/src/components/Footer.tsx` (in=1, out=0)
- `web/src/components/Header.tsx` (in=1, out=0)
- `web/src/App.tsx` (in=0, out=3)
