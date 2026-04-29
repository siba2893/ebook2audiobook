import asyncio
import json

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from routers.sessions import EVENT_QUEUES, ensure_event_queue, session_or_404


router = APIRouter(prefix="/api/sessions", tags=["events"])


def _drain_alerts(session: Any) -> list[dict[str, Any]]:
    alerts = session.get("alerts")
    if alerts is None:
        return []
    items = list(alerts)
    while len(alerts):
        alerts.pop(0)
    return items


@router.get("/{session_id}/events")
async def stream_session_events(session_id: str, request: Request) -> StreamingResponse:
    session = session_or_404(session_id)
    initial_queue = ensure_event_queue(session_id)

    async def event_stream():
        ping_interval = 15.0
        poll_interval = 0.5
        last_ping = asyncio.get_running_loop().time()
        current_queue = initial_queue
        while True:
            if await request.is_disconnected():
                break

            queue_meta = EVENT_QUEUES.get(session_id)
            if queue_meta and queue_meta["queue"] is not current_queue:
                current_queue = queue_meta["queue"]

            sent_payload = False
            try:
                item = await asyncio.wait_for(current_queue.get(), timeout=poll_interval)
                yield f"event: alert\ndata: {json.dumps(item)}\n\n"
                sent_payload = True
            except asyncio.TimeoutError:
                pass

            for item in _drain_alerts(session):
                yield f"event: alert\ndata: {json.dumps(item)}\n\n"
                sent_payload = True

            now = asyncio.get_running_loop().time()
            if not sent_payload and now - last_ping >= ping_interval:
                last_ping = now
                yield ": ping\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
