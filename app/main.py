import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, groups, expenses, settlements, invites, users, currencies
from app.routers.socket_events import sio

app = FastAPI(title="SplitEasy API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(groups.router)
app.include_router(expenses.router)
app.include_router(settlements.router)
app.include_router(invites.router)
app.include_router(users.router)
app.include_router(currencies.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


# Mount Socket.io — must be last
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)