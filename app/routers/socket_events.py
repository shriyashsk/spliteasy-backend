import socketio
from app.config import settings

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.cors_origins_list,
    logger=False,
    engineio_logger=False,
)


@sio.event
async def connect(sid, environ, auth):
    print(f"Socket connected: {sid}")


@sio.event
async def disconnect(sid):
    print(f"Socket disconnected: {sid}")


@sio.event
async def join_group(sid, data):
    group_id = data.get("group_id")
    if group_id:
        await sio.enter_room(sid, f"group:{group_id}")


@sio.event
async def join_expense(sid, data):
    expense_id = data.get("expense_id")
    if expense_id:
        await sio.enter_room(sid, f"expense:{expense_id}")


async def emit_balance_updated(group_id: str):
    await sio.emit("balance:updated", {"group_id": group_id}, room=f"group:{group_id}")


async def emit_comment_new(expense_id: str, comment: dict):
    await sio.emit("comment:new", {"expense_id": expense_id, "comment": comment}, room=f"expense:{expense_id}")