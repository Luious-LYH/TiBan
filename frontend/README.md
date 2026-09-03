# TiBan frontend

React + Vite + TypeScript frontend for the TiBan learning platform.

The current shell exposes four product surfaces:

- `/` — learning overview
- `/banks` — question bank catalog
- `/practice` — Practice with the persistent right-side Tutor
- `/eval` — 评测实验室（模型评测与 RAG 评测）

## Development

```bash
npm install
npm run dev
npm run lint
npm test -- --run
npm run build
```

The Docker stack serves the frontend on `http://127.0.0.1:5173` and the API on
`http://127.0.0.1:8000`. For a separately running backend, set
`VITE_API_BASE_URL`.

The TypeScript API contract is generated from FastAPI OpenAPI:

```bash
npm run api:generate
npm run api:check
```
