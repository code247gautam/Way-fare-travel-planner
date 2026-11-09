"""Wayfare FastAPI application – main entry point."""
from __future__ import annotations
import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .config import get_settings
from .models import (
    ChatRequest, ChatResponse,
    PlanRequest, PlanResponse,
    ShareRequest, ShareResponse, CollabTrip, Comment,
    TripPreferences, Itinerary,
)
from .models.providers import DisruptionAlert
from .models.trip import ReplanResult
from .agent.granite_client import get_granite_client
from .agent.planner import TravelPlanner
from .agent.replanner import SmartReplanner
from .db import get_cloudant_store, get_cos_store, get_appid_auth
from .services import (
    get_rail_service, get_weather_service, get_places_service,
    get_geocode_service, get_fx_service, get_flight_service,
    get_stays_service, get_bus_service, get_cab_service,
    get_airport_service, get_visa_service, get_photo_service,
    get_disruption_service,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Wayfare AI Travel Planner", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Dependency: current user (App ID or dev token) ───────────────────────────

async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    auth = get_appid_auth()
    token = ""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
    if not token:
        # Create anonymous dev token
        token = auth.create_dev_token(str(uuid.uuid4()))
    user = await auth.verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"user_id": user.user_id, "name": user.name, "email": user.email}


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "Wayfare", "powered_by": "IBM Granite"}


# ── Chat ─────────────────────────────────────────────────────────────────────

@app.post("/api/chat", response_model=ChatResponse)
@limiter.limit("30/minute")
async def chat(request: Request, body: ChatRequest, user: dict = Depends(get_current_user)):
    """Single-turn chat with Granite."""
    granite = get_granite_client()
    planner = TravelPlanner(granite)
    history = [{"role": m.role, "content": m.content} for m in body.history]
    reply = await planner.chat(body.message, history)
    return ChatResponse(
        session_id=body.session_id,
        reply=reply,
        trip_id=body.trip_id,
    )


# ── Plan ─────────────────────────────────────────────────────────────────────

@app.post("/api/plan", response_model=PlanResponse)
@limiter.limit("10/minute")
async def plan_trip(request: Request, body: PlanRequest, user: dict = Depends(get_current_user)):
    """Build a full itinerary from preferences."""
    granite = get_granite_client()
    planner = TravelPlanner(granite)
    itinerary = await planner.plan_trip(body.preferences)

    # Persist to Cloudant
    store = get_cloudant_store()
    doc = itinerary.model_dump()
    doc["user_id"] = user["user_id"]
    await store.put("trips", itinerary.trip_id, doc)

    # Create default share token (owner)
    share_token = str(uuid.uuid4()).replace("-", "")
    await store.put("shares", share_token, {
        "trip_id": itinerary.trip_id,
        "user_id": user["user_id"],
        "role": "owner",
        "created_at": datetime.utcnow().isoformat(),
    })

    return PlanResponse(trip_id=itinerary.trip_id, itinerary=itinerary, share_token=share_token)


# ── Extract preferences from chat ─────────────────────────────────────────────

@app.post("/api/extract-preferences")
@limiter.limit("20/minute")
async def extract_preferences(request: Request, body: dict, user: dict = Depends(get_current_user)):
    granite = get_granite_client()
    planner = TravelPlanner(granite)
    try:
        prefs = await planner.extract_preferences(
            body.get("message", ""),
            body.get("context", ""),
        )
        return {"preferences": prefs.model_dump(), "ready": prefs.clarifying_question is None}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ── Trip CRUD ────────────────────────────────────────────────────────────────

@app.get("/api/trips/{trip_id}")
async def get_trip(trip_id: str, user: dict = Depends(get_current_user)):
    store = get_cloudant_store()
    doc = await store.get("trips", trip_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Trip not found")
    return doc


@app.get("/api/trips")
async def list_trips(user: dict = Depends(get_current_user)):
    store = get_cloudant_store()
    docs = await store.query("trips", {"user_id": user["user_id"]})
    return {"trips": docs}


# ── Compare prices ────────────────────────────────────────────────────────────

@app.post("/api/compare")
@limiter.limit("20/minute")
async def compare_prices(request: Request, body: dict, user: dict = Depends(get_current_user)):
    origin = body.get("origin", "Delhi")
    destination = body.get("destination", "Mumbai")
    date_str = body.get("date")
    granite = get_granite_client()
    planner = TravelPlanner(granite)

    trains = await get_rail_service().search_trains(origin, destination, date_str)
    flights = await get_flight_service().search_flights(origin, destination, date_str)
    buses = await get_bus_service().search_buses(origin, destination, date_str)
    stays_list = await get_stays_service().search_stays(destination, date_str or "", "")

    planner._apply_badges(trains, flights, buses, stays_list)
    badge_map = getattr(planner, "_badge_map", {})
    granite_data = await planner.compare_prices(trains, flights, buses, stays_list)

    def _with_badges(item: dict, id_field: str) -> dict:
        sid = item.get(id_field, "")
        item["badges"] = badge_map.get(sid, [])
        return item

    return {
        "trains": [_with_badges(t.model_dump(), "train_number") for t in trains],
        "flights": [_with_badges(f.model_dump(), "flight_number") for f in flights],
        "buses": [_with_badges(b.model_dump(), "bus_id") for b in buses],
        "stays": [s.model_dump() for s in stays_list],
        "granite_reason": granite_data.get("granite_reason", ""),
        "best_value_id": granite_data.get("best_value_id", ""),
    }


# ── Smart Replan ──────────────────────────────────────────────────────────────

@app.post("/api/replan")
@limiter.limit("10/minute")
async def replan_trip(request: Request, body: dict, user: dict = Depends(get_current_user)):
    trip_id = body.get("trip_id")
    disruption = body.get("disruption")  # DisruptionAlert dict or simulate flag

    store = get_cloudant_store()
    trip_doc = await store.get("trips", trip_id)
    if not trip_doc:
        raise HTTPException(status_code=404, detail="Trip not found")

    # Verify ownership
    _enforce_role(trip_doc, user["user_id"], required_roles={"owner", "editor"})

    itinerary = Itinerary(**trip_doc)

    # Simulate disruption if requested
    if body.get("simulate"):
        service_id = body.get("service_id", "12951")
        service_type = body.get("service_type", "train")
        disruption_svc = get_disruption_service()
        alert = await disruption_svc.simulate_disruption(service_id, service_type)
    elif disruption:
        alert = DisruptionAlert(**disruption)
    else:
        raise HTTPException(status_code=400, detail="Provide disruption or simulate=true")

    granite = get_granite_client()
    replanner = SmartReplanner(granite)
    result = await replanner.replan(itinerary, alert)

    return result.model_dump()


@app.post("/api/replan/approve")
async def approve_replan(body: dict, user: dict = Depends(get_current_user)):
    trip_id = body.get("trip_id")
    after_days_raw = body.get("after_days", [])

    store = get_cloudant_store()
    trip_doc = await store.get("trips", trip_id)
    if not trip_doc:
        raise HTTPException(status_code=404, detail="Trip not found")
    _enforce_role(trip_doc, user["user_id"], required_roles={"owner", "editor"})

    trip_doc["days"] = after_days_raw
    trip_doc["replanned"] = True
    await store.put("trips", trip_id, trip_doc)
    return {"status": "approved", "trip_id": trip_id}


# ── Collaborative dashboard ───────────────────────────────────────────────────

@app.post("/api/share", response_model=ShareResponse)
async def share_trip(body: ShareRequest, user: dict = Depends(get_current_user)):
    store = get_cloudant_store()
    trip_doc = await store.get("trips", body.trip_id)
    if not trip_doc:
        raise HTTPException(status_code=404, detail="Trip not found")
    _enforce_role(trip_doc, user["user_id"], required_roles={"owner"})

    token = str(uuid.uuid4()).replace("-", "")
    await store.put("shares", token, {
        "trip_id": body.trip_id,
        "user_id": user["user_id"],
        "role": body.role,
        "invitee_email": body.invitee_email,
        "created_at": datetime.utcnow().isoformat(),
    })
    share_url = f"/shared?token={token}"
    return ShareResponse(share_token=token, share_url=share_url, role=body.role)


@app.get("/api/shared/{token}")
async def get_shared_trip(token: str, authorization: Optional[str] = Header(None)):
    store = get_cloudant_store()
    share_doc = await store.get("shares", token)
    if not share_doc:
        raise HTTPException(status_code=404, detail="Share link not found")

    trip_doc = await store.get("trips", share_doc["trip_id"])
    if not trip_doc:
        raise HTTPException(status_code=404, detail="Trip not found")

    # Get collab data
    collab = await store.get("collab", share_doc["trip_id"]) or {}

    return {
        "trip": trip_doc,
        "role": share_doc["role"],
        "comments": collab.get("comments", []),
        "checklist": collab.get("checklist", []),
        "budget_split": collab.get("budget_split", []),
        "last_updated": collab.get("last_updated", ""),
    }


@app.post("/api/shared/{token}/comment")
async def add_comment(token: str, body: dict, user: dict = Depends(get_current_user)):
    store = get_cloudant_store()
    share_doc = await store.get("shares", token)
    if not share_doc:
        raise HTTPException(status_code=403, detail="Invalid share token")
    # Viewers cannot comment in write-only mode; allow editors and owners
    _enforce_share_role(share_doc["role"], min_role="viewer")

    trip_id = share_doc["trip_id"]
    collab = await store.get("collab", trip_id) or {"comments": [], "checklist": [], "budget_split": []}
    comment = {
        "comment_id": str(uuid.uuid4()),
        "author_id": user["user_id"],
        "author_name": user.get("name", "Traveller"),
        "item_ref": body.get("item_ref"),
        "text": body.get("text", ""),
        "created_at": datetime.utcnow().isoformat(),
    }
    collab["comments"].append(comment)
    collab["last_updated"] = datetime.utcnow().isoformat()
    await store.put("collab", trip_id, collab)
    return comment


@app.put("/api/shared/{token}/checklist/{item_id}")
async def update_checklist(token: str, item_id: str, body: dict, user: dict = Depends(get_current_user)):
    store = get_cloudant_store()
    share_doc = await store.get("shares", token)
    if not share_doc:
        raise HTTPException(status_code=403, detail="Invalid share token")
    _enforce_share_role(share_doc["role"], min_role="editor")

    trip_id = share_doc["trip_id"]
    collab = await store.get("collab", trip_id) or {"comments": [], "checklist": [], "budget_split": []}
    for item in collab.get("checklist", []):
        if item["item_id"] == item_id:
            item["done"] = body.get("done", item["done"])
    collab["last_updated"] = datetime.utcnow().isoformat()
    await store.put("collab", trip_id, collab)
    return {"status": "updated"}


# ── Provider passthrough endpoints ────────────────────────────────────────────

@app.get("/api/weather/{city}")
async def get_weather(city: str):
    svc = get_weather_service()
    result = await svc.get_weather(city)
    return result.model_dump()


@app.get("/api/trains")
async def search_trains(origin: str, destination: str, date: Optional[str] = None):
    svc = get_rail_service()
    results = await svc.search_trains(origin, destination, date)
    return [r.model_dump() for r in results]


@app.get("/api/flights")
async def search_flights(origin: str, destination: str, date: Optional[str] = None):
    svc = get_flight_service()
    results = await svc.search_flights(origin, destination, date)
    return [r.model_dump() for r in results]


@app.get("/api/buses")
async def search_buses(origin: str, destination: str, date: Optional[str] = None):
    svc = get_bus_service()
    results = await svc.search_buses(origin, destination, date)
    return [r.model_dump() for r in results]


@app.get("/api/stays")
async def search_stays(city: str, check_in: str = "", check_out: str = ""):
    svc = get_stays_service()
    results = await svc.search_stays(city, check_in, check_out)
    return [r.model_dump() for r in results]


@app.get("/api/geocode")
async def geocode(query: str):
    svc = get_geocode_service()
    result = await svc.geocode(query)
    return result.model_dump()


@app.get("/api/places")
async def find_places(city: str, category: str = "tourism"):
    svc = get_places_service()
    results = await svc.find_places(city, category)
    return [r.model_dump() for r in results]


@app.get("/api/fx")
async def convert_currency(amount: float, from_currency: str, to_currency: str):
    svc = get_fx_service()
    result = await svc.convert(amount, from_currency, to_currency)
    return result.model_dump()


@app.get("/api/airports")
async def search_airports(query: str):
    svc = get_airport_service()
    results = await svc.search_airports(query)
    return [r.model_dump() for r in results]


@app.get("/api/visa")
async def get_visa_info(destination_country: str, nationality: str = "Indian"):
    svc = get_visa_service()
    result = await svc.get_visa_info(nationality, destination_country)
    return result.model_dump()


@app.get("/api/photos/{place}")
async def get_photos(place: str):
    svc = get_photo_service()
    result = await svc.get_photos(place)
    return result.model_dump()


@app.get("/api/disruptions")
async def check_disruptions(train_numbers: str = "", flight_numbers: str = ""):
    svc = get_disruption_service()
    trains = [t.strip() for t in train_numbers.split(",") if t.strip()] or None
    flights = [f.strip() for f in flight_numbers.split(",") if f.strip()] or None
    results = await svc.check_disruptions(trains, flights)
    return [r.model_dump() for r in results]


# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.get("/api/auth/dev-login")
async def dev_login():
    """Development login – creates a dev token."""
    auth = get_appid_auth()
    uid = str(uuid.uuid4())
    token = auth.create_dev_token(uid)
    return {"token": token, "user_id": uid, "name": "Dev User", "mode": "development"}


@app.get("/api/auth/login")
async def login():
    auth = get_appid_auth()
    return {"login_url": auth.get_login_url()}


# ── Export itinerary to COS ───────────────────────────────────────────────────

@app.post("/api/export/{trip_id}")
async def export_itinerary(trip_id: str, user: dict = Depends(get_current_user)):
    store = get_cloudant_store()
    trip_doc = await store.get("trips", trip_id)
    if not trip_doc:
        raise HTTPException(status_code=404, detail="Trip not found")
    cos = get_cos_store()
    import json as _json
    data = _json.dumps(trip_doc, indent=2).encode()
    url = await cos.upload(f"exports/{trip_id}.json", data, "application/json")
    return {"url": url, "trip_id": trip_id}


# ── Role enforcement helpers ──────────────────────────────────────────────────

def _enforce_role(trip_doc: dict, user_id: str, required_roles: set[str]) -> None:
    if trip_doc.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")


def _enforce_share_role(actual_role: str, min_role: str) -> None:
    role_order = {"owner": 0, "editor": 1, "viewer": 2}
    if role_order.get(actual_role, 99) > role_order.get(min_role, 99):
        raise HTTPException(status_code=403, detail=f"Requires at least {min_role} role")


# ── __init__ for backend package ──────────────────────────────────────────────

