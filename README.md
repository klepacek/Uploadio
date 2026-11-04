# Uploadio

A social publishing workspace for Instagram and TikTok, owned by **Vojtěch Klepáček** ([klepacek](https://github.com/klepacek)).

Development is in progress. Live publishing requires platform credentials and approval; no mock publisher is used in production.

## Development

Python 3.12+, Node.js 22+, PostgreSQL 16+, Redis 7+, and FFmpeg are required.

```sh
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload
```

```sh
cd frontend
npm ci
npm run dev
```

API documentation: http://localhost:8000/docs. Milestone progress and deployment instructions will be maintained in `docs/`.
