"""Strict JSON schemas for every Granite agent tool."""
from __future__ import annotations

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "search_destinations",
        "description": "Find information and geocoordinates for a travel destination.",
        "parameters": {
            "type": "object",
            "properties": {
                "destination": {"type": "string", "description": "City or country name"},
            },
            "required": ["destination"],
        },
    },
    {
        "name": "geocode",
        "description": "Convert a place name to latitude and longitude.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Place name to geocode"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_weather",
        "description": "Get current weather or forecast for a city.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "date": {"type": "string", "description": "ISO date YYYY-MM-DD, optional"},
            },
            "required": ["city"],
        },
    },
    {
        "name": "find_places",
        "description": "Find points of interest (monuments, restaurants, parks) in a city.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "category": {"type": "string", "enum": ["tourism", "catering", "entertainment", "natural", "commercial"]},
            },
            "required": ["city"],
        },
    },
    {
        "name": "get_route",
        "description": "Get driving/walking route between two points.",
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {"type": "string"},
                "destination": {"type": "string"},
                "mode": {"type": "string", "enum": ["drive", "walk", "bicycle"], "default": "drive"},
            },
            "required": ["origin", "destination"],
        },
    },
    {
        "name": "search_trains",
        "description": "Search for train options between two stations or cities.",
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "Station code or city"},
                "destination": {"type": "string"},
                "date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
            },
            "required": ["origin", "destination"],
        },
    },
    {
        "name": "search_flights",
        "description": "Search for flights between two airports or cities.",
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "IATA code or city"},
                "destination": {"type": "string"},
                "date": {"type": "string"},
            },
            "required": ["origin", "destination"],
        },
    },
    {
        "name": "search_buses",
        "description": "Search for bus services between two cities.",
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {"type": "string"},
                "destination": {"type": "string"},
                "date": {"type": "string"},
            },
            "required": ["origin", "destination"],
        },
    },
    {
        "name": "estimate_cab",
        "description": "Estimate cab fare and travel time between two points.",
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {"type": "string"},
                "destination": {"type": "string"},
                "cab_type": {"type": "string", "enum": ["Auto", "Hatchback", "Sedan", "SUV", "Luxury"], "default": "Sedan"},
            },
            "required": ["origin", "destination"],
        },
    },
    {
        "name": "search_stays",
        "description": "Search for accommodation (homes, apartments) in a city.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "check_in": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "check_out": {"type": "string", "description": "ISO date YYYY-MM-DD"},
            },
            "required": ["city", "check_in", "check_out"],
        },
    },
    {
        "name": "compare_prices",
        "description": "Compare transport or stay options and add Cheapest/Fastest/Best Value badges.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": ["transport", "stays"]},
                "origin": {"type": "string"},
                "destination": {"type": "string"},
                "date": {"type": "string"},
            },
            "required": ["category"],
        },
    },
    {
        "name": "convert_currency",
        "description": "Convert an amount between currencies.",
        "parameters": {
            "type": "object",
            "properties": {
                "amount": {"type": "number"},
                "from_currency": {"type": "string", "description": "ISO 4217 code, e.g. USD"},
                "to_currency": {"type": "string", "description": "ISO 4217 code, e.g. INR"},
            },
            "required": ["amount", "from_currency", "to_currency"],
        },
    },
    {
        "name": "build_itinerary",
        "description": "Assemble a day-by-day itinerary from gathered data.",
        "parameters": {
            "type": "object",
            "properties": {
                "preferences": {"type": "object", "description": "TripPreferences JSON"},
                "transport": {"type": "array", "items": {"type": "object"}},
                "stays": {"type": "array", "items": {"type": "object"}},
                "places": {"type": "array", "items": {"type": "object"}},
                "weather": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["preferences"],
        },
    },
    {
        "name": "check_disruptions",
        "description": "Check for real-time train or flight cancellations and delays.",
        "parameters": {
            "type": "object",
            "properties": {
                "train_numbers": {"type": "array", "items": {"type": "string"}},
                "flight_numbers": {"type": "array", "items": {"type": "string"}},
            },
            "required": [],
        },
    },
    {
        "name": "replan_trip",
        "description": "Replan remaining journey after a disruption.",
        "parameters": {
            "type": "object",
            "properties": {
                "trip_id": {"type": "string"},
                "disruption_description": {"type": "string"},
                "affected_leg": {"type": "string"},
            },
            "required": ["trip_id", "disruption_description"],
        },
    },
    {
        "name": "share_trip",
        "description": "Generate a shareable link for a trip.",
        "parameters": {
            "type": "object",
            "properties": {
                "trip_id": {"type": "string"},
                "role": {"type": "string", "enum": ["viewer", "editor"]},
            },
            "required": ["trip_id"],
        },
    },
    {
        "name": "get_visa_info",
        "description": "Get visa requirements for a destination country.",
        "parameters": {
            "type": "object",
            "properties": {
                "nationality": {"type": "string", "default": "Indian"},
                "destination_country": {"type": "string"},
            },
            "required": ["destination_country"],
        },
    },
    {
        "name": "get_destination_photos",
        "description": "Get photos for a city or destination.",
        "parameters": {
            "type": "object",
            "properties": {
                "place": {"type": "string"},
            },
            "required": ["place"],
        },
    },
]
