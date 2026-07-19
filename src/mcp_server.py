"""
mcp_server.py
=============
NexCell AI – Voice Assistant MCP Server Layer
Implements three core domain tools via FastMCP:
  1. check_availability  – Room / slot availability checker
  2. create_booking      – Booking / reservation engine
  3. search_faq          – Semantic-style FAQ search over an in-memory store

Run with:
    python mcp_server.py
The server will start on http://127.0.0.1:8000 using Streamable-HTTP transport.
"""

from __future__ import annotations

import os
import re
import random
import uuid
import datetime
import json

import sys
from pathlib import Path
from typing import Literal

# ---------------------------------------------------------------------------
# Strict Startup Validation for Deployment
# ---------------------------------------------------------------------------
# Priority: PUBLIC_URL (explicit) > RENDER_EXTERNAL_URL (Render auto) > SPACE_ID (HF) > localhost
if os.environ.get("PUBLIC_URL"):
    PUBLIC_URL = os.environ["PUBLIC_URL"].rstrip("/")
elif os.environ.get("RENDER_EXTERNAL_URL"):
    PUBLIC_URL = os.environ["RENDER_EXTERNAL_URL"].rstrip("/")
elif os.environ.get("SPACE_ID"):
    raise ValueError("CRITICAL ERROR: PUBLIC_URL environment variable is required on Hugging Face.")
else:
    PUBLIC_URL = "http://127.0.0.1:7860"

from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

# Load environment variables
load_dotenv()

import sys
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from fastmcp import FastMCP
from pydantic import BaseModel, Field, field_validator
from starlette.requests import Request
from starlette.responses import JSONResponse, HTMLResponse
from starlette.routing import Route
from starlette.applications import Starlette
import uvicorn

# ---------------------------------------------------------------------------
# Server initialisation
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "NexCellServicesMCP",
    instructions=(
        "Provides hotel availability checks, booking management, "
        "and FAQ lookup for the NexCell voice assistant."
    ),
    version="2026.1.0",
)

# ---------------------------------------------------------------------------
# In-memory mock data stores
# ---------------------------------------------------------------------------

from src.database import (
    get_availability, create_booking as db_create_booking, 
    get_booking, modify_booking_room, modify_booking_name, 
    cancel_booking as db_cancel_booking, get_payment_history, INVENTORY_CAPACITY
)

# FAQ knowledge base: list of {question, answer, tags}
_FAQ_STORE: list[dict[str, str]] = [
    # -----------------------------------------------------------------------
    # Common amenities — all branches
    # -----------------------------------------------------------------------
    {
        "question": "What amenities do you have? What facilities are available?",
        "answer": (
            "Every NexCell branch offers a superb set of standard five-star amenities: "
            "complimentary 1 Gbps Wi-Fi throughout the building, "
            "a fully equipped in-house gym open 24 hours, "
            "a heated indoor swimming pool with jacuzzi, "
            "a sauna and steam wellness suite, "
            "an in-house restaurant and bar open 24 hours, "
            "24-hour room service, "
            "complimentary on-site parking, "
            "a business centre with private meeting rooms, "
            "and a concierge and valet service. "
            "Complimentary breakfast is included for all Deluxe Double and Executive Suite guests. "
            "And each of our branches has its own signature experience — "
            "which branch are you planning to stay at? I'd love to tell you what makes it truly special."
        ),
        "tags": "amenities gym swimming pool wifi dining restaurant bar room service concierge parking business lounge wellness sauna jacuzzi breakfast",
    },
    {
        "question": "Do you have a gym or fitness centre?",
        "answer": (
            "Absolutely — all our branches have a state-of-the-art gym facility open 24 hours a day. "
            "It's fully equipped with treadmills, free weights, cable machines, and a dedicated yoga zone. "
            "Complimentary towels and refreshments are provided."
        ),
        "tags": "gym fitness workout exercise weights yoga 24 hour",
    },
    {
        "question": "Do you have a swimming pool?",
        "answer": (
            "Yes! All NexCell branches feature a beautiful heated indoor swimming pool with a jacuzzi. "
            "Pool towels are complimentary and available throughout the day."
        ),
        "tags": "swimming pool jacuzzi heated indoor",
    },
    {
        "question": "Is there Wi-Fi?",
        "answer": (
            "Complimentary ultra-high-speed Wi-Fi — up to 1 Gbps — is available throughout every NexCell Hotel, "
            "in all guest rooms, the lobby, restaurant, pool area, and meeting rooms."
        ),
        "tags": "wifi internet connection speed broadband",
    },
    {
        "question": "What dining options do you have? Is there a restaurant?",
        "answer": (
            "Every branch has an in-house restaurant and bar open 24 hours a day. "
            "We serve a full cooked breakfast from 7 AM, an à la carte lunch menu, "
            "and a contemporary dinner menu crafted by our executive chef. "
            "24-hour room service is also available for guests who prefer dining in their room."
        ),
        "tags": "dining restaurant food breakfast lunch dinner room service bar 24 hour",
    },
    {
        "question": "Is breakfast included?",
        "answer": (
            "Complimentary breakfast is included as standard for Deluxe Double and Executive Suite guests — "
            "a full continental and cooked English breakfast served daily from 7 AM to 10:30 AM. "
            "Standard Twin guests can add it for just £15 per person per day."
        ),
        "tags": "breakfast included complimentary deluxe executive standard twin",
    },
    {
        "question": "What room types do you have and what are their guest capacities?",
        "answer": (
            "We offer three luxurious room types across all our branches: "
            "1) Standard Twin, which comfortably accommodates up to 4 guests. "
            "2) Deluxe Double, designed for up to 5 guests. "
            "3) Premium Suite (our Executive Suite), which allows for 2 guests plus 1 child."
        ),
        "tags": "room type capacity guests standard twin deluxe double premium suite executive how many",
    },
    {
        "question": "What exclusive amenities do Premium Suite guests receive?",
        "answer": (
            "Our Premium Suites offer the ultimate luxury experience. Across all three branches, "
            "Premium Suite guests enjoy an unlimited food selection across all hotel restaurants, "
            "along with unlimited dessert snacks and refreshments through our 24-hour room service."
        ),
        "tags": "premium suite executive exclusive unlimited food dessert snacks refreshments room service",
    },
    # -----------------------------------------------------------------------
    # Branch-specific unique amenities — exact per user specification
    # -----------------------------------------------------------------------
    {
        "question": "What unique amenities does the London branch have? What is special about London?",
        "answer": (
            "Our London branch is our crown jewel. "
            "As a guest, you'll enjoy complimentary fine dining at our on-site Michelin-star restaurant. "
            "You'll also receive three complimentary tickets per guest to iconic London landmarks — "
            "think the Tower of London, the Shard, or Buckingham Palace. "
            "On top of that, we include a complimentary taxi transfer to any one destination of your choice in the city. "
            "You'll also have access to the NexCell Prestige Spa — a stunning 3,000 square foot luxury treatment centre — "
            "and our rooftop infinity pool and sky bar on the 15th floor with breathtaking panoramic views of the London skyline."
        ),
        "tags": "london unique fine dining michelin star tickets monuments landmarks taxi spa rooftop infinity pool sky bar",
    },
    {
        "question": "What unique amenities does the Manchester branch have? What is special about Manchester?",
        "answer": (
            "Manchester is full of energy, and our hotel delivers that in spades. "
            "Exclusive highlights include private cinema rooms you can book by the hour, "
            "a complimentary private airport drop included with Premium Suite stays, "
            "a full-service luxury in-house spa, "
            "and a complimentary activity pass valid across five of Manchester's most iconic nearby attractions of your choice. "
            "It's the ultimate urban staycation."
        ),
        "tags": "manchester unique cinema room private airport drop luxury spa activity pass attractions monuments",
    },
    {
        "question": "What unique amenities does the Edinburgh branch have? What is special about Edinburgh?",
        "answer": (
            "Edinburgh is our most immersive and experiential destination. "
            "Guests enjoy an on-site ice skating rink — perfect for a magical winter visit — "
            "alongside fine dining with a curated Scottish tasting menu by our head chef. "
            "The property also features a traditional Hammam spa with steam rituals and therapeutic treatments, "
            "and a stunning heated artificial lagoon for relaxing outdoor bathing year-round. "
            "The Scottish Spirits Bar inside the hotel features over 200 rare single malts, "
            "and guided Highland hiking tours depart directly from the hotel."
        ),
        "tags": "edinburgh unique ice skating rink fine dining scottish tasting menu hammam spa artificial lagoon whisky spirits bar highland hiking",
    },
    # -----------------------------------------------------------------------
    # Hotel policies
    # -----------------------------------------------------------------------
    {
        "question": "What is the check-in and check-out time?",
        "answer": (
            "Check-in begins at 3 PM and check-out is by 11 AM. "
            "We offer complimentary luggage storage if you arrive earlier. "
            "Early check-in from 12 PM and late check-out until 2 PM are available on request, subject to availability."
        ),
        "tags": "check-in check-out time early late luggage",
    },
    {
        "question": "What is the cancellation policy?",
        "answer": (
            "Cancellations made 48 hours or more before check-in receive a full refund. "
            "Cancellations within 48 hours forfeit the first night's charge as a late cancellation fee."
        ),
        "tags": "cancellation refund policy cancel 48 hours",
    },
    {
        "question": "Is parking available at the hotel?",
        "answer": (
            "Complimentary on-site parking is available at all our branches. "
            "London guests should note the hotel is within the Congestion Charge zone, "
            "though parking in our hotel grounds is always free."
        ),
        "tags": "parking car vehicle congestion london free",
    },
    {
        "question": "Do you accept pets?",
        "answer": (
            "Well-behaved dogs are warmly welcome at our Manchester and Edinburgh branches, "
            "with a small surcharge of £25 per night. "
            "Unfortunately, pets are not permitted at our London branch."
        ),
        "tags": "pets dog animal manchester edinburgh london",
    },
    {
        "question": "How do I modify or amend an existing booking?",
        "answer": (
            "Of course — please have your booking reference ready and let me know the changes. "
            "Amendments are subject to availability and any applicable rate differences."
        ),
        "tags": "modify amend change booking reference",
    },
    {
        "question": "Are accessible or disability-friendly rooms available?",
        "answer": (
            "Yes, all NexCell branches have fully accessible rooms with roll-in showers, "
            "wide doorways, lowered fixtures, and hearing-loop systems. "
            "We recommend requesting one at booking to guarantee availability."
        ),
        "tags": "accessible disability wheelchair hearing loop shower",
    },
    {
        "question": "Is there a loyalty programme or membership?",
        "answer": (
            "Yes! Our NexCell Prestige Club is completely free to join. "
            "Every night you stay earns points redeemable for complimentary nights, spa treatments, or dining credits. "
            "Just ask at reception on check-in to sign up."
        ),
        "tags": "loyalty points membership club prestige rewards",
    },
    {
        "question": "Are there meeting rooms or business facilities?",
        "answer": (
            "All branches have a fully equipped business centre with private meeting rooms, "
            "video conferencing, high-speed internet, and catering options. "
            "Rooms can be booked by the hour or day — ask reception for availability."
        ),
        "tags": "meeting room business conference corporate video call",
    },
]


# ---------------------------------------------------------------------------
# Pydantic request / response schemas
# ---------------------------------------------------------------------------



class AvailabilityRequest(BaseModel):
    """Input schema for the availability checker tool."""

    branch: str = Field(
        ...,
        description=(
            "Hotel branch / city name, e.g. 'London', 'Manchester', 'Edinburgh'. "
            "Case-insensitive."
        ),
    )
    arrival_date: str = Field(
        ...,
        description="Desired arrival date in ISO format YYYY-MM-DD.",
    )
    nights: int = Field(
        default=1,
        ge=1,
        le=30,
        description="Number of nights for the stay (1–30).",
    )
    room_type: str | None = Field(
        default=None,
        description=(
            "Optional room type filter: 'standard_twin', 'deluxe_double', "
            "or 'executive_suite'. Leave blank to return all types."
        ),
    )

    @field_validator("arrival_date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        try:
            datetime.date.fromisoformat(v)
        except ValueError as exc:
            raise ValueError(
                f"arrival_date must be in YYYY-MM-DD format, got '{v}'."
            ) from exc
        return v


class BookingRequest(BaseModel):
    """Input schema for the booking engine tool."""

    guest_full_name: str = Field(
        ...,
        min_length=2,
        description="Full legal name of the primary guest.",
    )
    branch: str = Field(
        ...,
        description="Hotel branch / city name (case-insensitive).",
    )
    room_type: Literal["standard_twin", "deluxe_double", "executive_suite"] = Field(
        ...,
        description="Room category to reserve.",
    )
    arrival_date: str = Field(
        ...,
        description="Check-in date in YYYY-MM-DD format.",
    )
    nights: int = Field(
        default=1,
        ge=1,
        le=30,
        description="Number of nights for the stay (1–30).",
    )
    guest_email: str | None = Field(
        default=None,
        description="Optional guest e-mail address for confirmation.",
    )

    @field_validator("arrival_date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        try:
            datetime.date.fromisoformat(v)
        except ValueError as exc:
            raise ValueError(
                f"arrival_date must be in YYYY-MM-DD format, got '{v}'."
            ) from exc
        return v


class FAQRequest(BaseModel):
    """Input schema for the FAQ search tool."""

    query: str = Field(
        ...,
        min_length=2,
        description="Natural-language question or keywords to search the FAQ knowledge base.",
    )
    max_results: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum number of FAQ entries to return (1–10).",
    )


class InvoiceRequest(BaseModel):
    """Input schema for the invoice sender tool."""

    booking_id: str = Field(
        ...,
        description="The unique booking reference ID (e.g., NX-1234).",
    )
    email_address: str = Field(
        ...,
        description="The guest's email address.",
    )


# ---------------------------------------------------------------------------
# Tool 1 – Availability Checker
# ---------------------------------------------------------------------------


@mcp.tool()
async def check_availability(
    branch: str,
    arrival_date: str,
    nights: int = 1,
    room_type: str | None = None,
) -> str:
    """Check room availability and nightly pricing at a given NexCell branch, date, and optional room type. Returns available units and total cost in GBP."""
    payload = AvailabilityRequest(
        branch=branch,
        arrival_date=arrival_date,
        nights=nights,
        room_type=room_type
    )
    branch_key = payload.branch.strip().lower()

    if branch_key not in INVENTORY_CAPACITY:
        available_branches = ", ".join(sorted(INVENTORY_CAPACITY.keys()))
        return (
            f"ERROR: Branch '{payload.branch}' not recognised. "
            f"Available branches: {available_branches}."
        )

    date_inventory = get_availability(branch_key, payload.arrival_date)

    if payload.room_type:
        rt_key = payload.room_type.strip().lower().replace(" ", "_")
        if rt_key not in date_inventory:
            valid_types = ", ".join(date_inventory.keys())
            return (
                f"ERROR: Room type '{payload.room_type}' not available at "
                f"'{payload.branch}'. Valid types: {valid_types}."
            )
        date_inventory = {rt_key: date_inventory[rt_key]}

    lines: list[str] = [
        f"Availability at NexCell {payload.branch.title()} \n"
        f"from {payload.arrival_date} for {payload.nights} night(s):",
    ]
    any_available = False
    for rt, info in date_inventory.items():
        units = info["units"]
        price = info["price_gbp"]
        total = price * payload.nights
        label = rt.replace("_", " ").title()
        if units > 0:
            any_available = True
            lines.append(
                f"  • {label}: {units} unit(s) available | "
                f"£{price}/night | Total: £{total} for {payload.nights} night(s)."
            )
        else:
            lines.append(f"  • {label}: SOLD OUT on this date.")

    if not any_available:
        lines.append("No rooms are currently available for this selection.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 2 – Booking Engine
# ---------------------------------------------------------------------------


@mcp.tool()
async def create_booking(
    guest_full_name: str,
    branch: str,
    room_type: str,
    arrival_date: str,
    nights: int = 1,
    guest_email: str | None = None,
) -> str:
    """Create a reservation. Validates availability, generates a unique HTL reference, and persists the record as LOCKED."""
    payload = BookingRequest(
        guest_full_name=guest_full_name,
        branch=branch,
        room_type=room_type,  # type: ignore
        arrival_date=arrival_date,
        nights=nights,
        guest_email=guest_email
    )
    branch_key = payload.branch.strip().lower()

    if branch_key not in INVENTORY_CAPACITY:
        available_branches = ", ".join(sorted(INVENTORY_CAPACITY.keys()))
        return f"ERROR: Branch '{payload.branch}' not recognised. Available branches: {available_branches}."

    date_inventory = get_availability(branch_key, payload.arrival_date)
    rt_key = payload.room_type.strip().lower().replace(" ", "_")

    if rt_key not in date_inventory:
        return f"ERROR: Room type '{payload.room_type}' does not exist at '{payload.branch}'."

    room_info = date_inventory[rt_key]
    if room_info["units"] <= 0:
        return f"ERROR: '{payload.room_type.replace('_', ' ').title()}' is sold out at NexCell {payload.branch.title()} on {payload.arrival_date}."

    total_cost = room_info["price_gbp"] * payload.nights

    booking_ref = db_create_booking(
        guest_name=payload.guest_full_name,
        guest_email=payload.guest_email or "not provided",
        branch=branch_key,
        room_type=rt_key,
        arrival_date=payload.arrival_date,
        nights=payload.nights,
        price_per_night=room_info["price_gbp"],
        total_cost=total_cost
    )

    label = rt_key.replace("_", " ").title()
    arrival = datetime.date.fromisoformat(payload.arrival_date)
    checkout = arrival + datetime.timedelta(days=payload.nights)
    
    confirmation = (
        f"[LOCKED] Booking Locked for 24 hours!\\n"
        f"  Reference     : {booking_ref}\\n"
        f"  Guest         : {payload.guest_full_name}\\n"
        f"  Hotel         : NexCell {payload.branch.title()}\\n"
        f"  Room          : {label}\\n"
        f"  Check-in      : {payload.arrival_date}\\n"
        f"  Check-out     : {checkout}\\n"
        f"  Duration      : {payload.nights} night(s)\\n"
        f"  Total Cost    : £{total_cost} (£{room_info['price_gbp']}/night)\\n"
        f"  Status        : LOCKED\\n"
        f"IMPORTANT: Payment must be completed within 24 hours to confirm the booking."
    )
    return confirmation

@mcp.tool()
async def lookup_booking(reference: str) -> str:
    """Look up the details of an existing booking by its reference number."""
    booking = get_booking(reference)
    if not booking:
        return f"ERROR: Booking reference '{reference}' not found."
    return f"Booking Details:\n" + "\n".join([f"  {k}: {v}" for k, v in booking.items()])

@mcp.tool()
async def modify_booking(reference: str, new_room_type: str = "", new_guest_name: str = "") -> str:
    """Modify a booking. Can change room type or guest name. Does not support date changes."""
    booking = get_booking(reference)
    if not booking:
        return f"ERROR: Booking reference '{reference}' not found."
    
    msgs = []
    current_ref = reference
    if new_room_type:
        try:
            res = modify_booking_room(current_ref, new_room_type)
            current_ref = res["new_reference"]
            msgs.append(f"Room type changed to {new_room_type}. New Reference: {current_ref}. Price Difference: £{res['price_difference']}. New Total: £{res['new_total']}.")
        except Exception as e:
            msgs.append(f"ERROR changing room type: {e}")
            
    if new_guest_name:
        success = modify_booking_name(current_ref, new_guest_name)
        if success:
            msgs.append(f"Guest name updated to {new_guest_name}.")
            
    return "\n".join(msgs) if msgs else "No changes requested."

@mcp.tool()
async def cancel_reservation(reference: str) -> str:
    """Cancel a booking by reference."""
    if db_cancel_booking(reference):
        return f"SUCCESS: Booking '{reference}' cancelled successfully."
    return f"ERROR: Booking '{reference}' not found."



# ---------------------------------------------------------------------------
# Tool 3 – FAQ Search
# ---------------------------------------------------------------------------


@mcp.tool()
async def search_faq(
    query: str,
    max_results: int = 3,
) -> str:
    """Search the NexCell FAQ knowledge base by keyword. Returns the top matching question-and-answer entries."""
    payload = FAQRequest(
        query=query,
        max_results=max_results
    )
    query_tokens = set(payload.query.lower().split())

    scored: list[tuple[int, dict]] = []
    for entry in _FAQ_STORE:
        haystack = (entry["question"] + " " + entry["tags"]).lower()
        score = sum(1 for token in query_tokens if token in haystack)
        if score > 0:
            scored.append((score, entry))

    # Sort by descending relevance score
    scored.sort(key=lambda x: x[0], reverse=True)
    top_results = scored[: payload.max_results]

    if not top_results:
        return (
            "No FAQ entries matched your query. "
            "Please contact our support team for further assistance."
        )

    lines: list[str] = [
        f"Found {len(top_results)} FAQ result(s) for query: '{payload.query}'\n"
    ]
    for rank, (score, entry) in enumerate(top_results, start=1):
        lines.append(f"[{rank}] Q: {entry['question']}")
        lines.append(f"    A: {entry['answer']}")
        lines.append(f"    (Relevance score: {score})\n")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 4 – Send Invoice
# ---------------------------------------------------------------------------

# send_invoice is defined after _generate_invoice_html below.

# ---------------------------------------------------------------------------
# Utility – Email & HTML Generation
# ---------------------------------------------------------------------------

def _send_email_resend(to_email: str, subject: str, html_content: str) -> bool:
    import os
    import resend

    resend_api_key = os.environ.get("RESEND_API_KEY")
    if not resend_api_key:
        print("WARNING: RESEND_API_KEY missing in .env, skipping email.")
        return False
        
    resend.api_key = resend_api_key
    sender = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
    
    try:
        params: resend.Emails.SendParams = {
            "from": sender,
            "to": [to_email],
            "subject": subject,
            "html": html_content,
        }
        resend.Emails.send(params)
        return True
    except Exception as e:
        print(f"ERROR sending email via Resend: {e}")
        return False

# send_invoice is defined below at line 808.

# ---------------------------------------------------------------------------
# Standalone HTTP API (zero-LLM invoice endpoints)
# These are called directly by voice_server.py — no AI tokens consumed.
# ---------------------------------------------------------------------------

async def _generate_invoice_html(booking_id: str, email_address: str) -> tuple[bool, str]:
    """
    Core invoice generation logic — reads from SQLite DB.
    Returns (success: bool, message: str).
    On success the HTML is saved to invoices/invoice_<booking_id>.html
    and an SMTP email is attempted if credentials are configured.
    """
    booking = get_booking(booking_id)
    if not booking:
        return False, f"ERROR: Booking reference '{booking_id}' not found."

    arr_date = datetime.date.fromisoformat(booking["arrival_date"])
    checkout_date = datetime.date.fromisoformat(booking["checkout_date"])

    branch_key = booking["branch"].lower()
    room_key   = booking["room_type"]
    price_per_night = int(booking["price_per_night"])
    total_amount    = int(booking["total_cost"])

    branch_addresses = {
        "london":     ("42 Regent Street,<br>London,<br>W1B 5TR,<br>United Kingdom.",   "42 Regent Street, London, W1B 5TR, UK."),
        "manchester": ("15 Deansgate,<br>Manchester,<br>M3 1AZ,<br>United Kingdom.",     "15 Deansgate, Manchester, M3 1AZ, UK."),
        "edinburgh":  ("105 Victoria St,<br>Edinburgh,<br>EH1 2EX,<br>United Kingdom.", "105 Victoria St, Edinburgh, EH1 2EX, UK."),
    }
    address_html, address_inline = branch_addresses.get(
        branch_key,
        ("1220 Ocean View Drive,<br>Seaside Cover, CA,<br>United States.",
         "1220 Ocean View Drive, Seaside Cover, CA, US."),
    )

    room_label = room_key.replace("_", " ").title()
    if room_key == "executive_suite":
        room_label = "Premium Suite"

    guest_str = (
        "Up to 4 Guests" if room_key == "standard_twin"
        else "Up to 5 Guests" if room_key == "deluxe_double"
        else "2 Adults, 1 Child"
    )
    room_img = (
        "Standard_twin.jpg" if room_key == "standard_twin"
        else "deluxe_double.jpg" if room_key == "deluxe_double"
        else "executive_room.jpg"
    )

    room_amenities: list[str] = []
    if room_key != "standard_twin":
        room_amenities.append(f"<img src='{PUBLIC_URL}/assets/images/breakfast.png' alt='Breakfast'> Breakfast")
    else:
        room_amenities.append("Standard Setup")
    if room_key == "executive_suite":
        room_amenities.append(f"<img src='{PUBLIC_URL}/assets/images/dining.png' alt='Dining'> Fine Dining")
        room_amenities.append(f"<img src='{PUBLIC_URL}/assets/images/refreshments.png' alt='Snacks'> Refreshments")

    # Choose template based on payment status
    template_name = (
        "confirmation_invoice_template.html"
        if booking["status"] == "BOOKED"
        else "invoice_template.html"
    )
    jinja_env = Environment(loader=FileSystemLoader(str(PROJECT_ROOT / "templates")))
    try:
        template = jinja_env.get_template(template_name)
    except Exception as exc:
        return False, f"ERROR: Could not load template '{template_name}': {exc}"

    # Fetch payment history to compute balances
    payments = get_payment_history(booking_id)
    total_paid = sum(p["amount_gbp"] for p in payments if p["status"] == "COMPLETED")
    balance_due = total_amount - total_paid
    refund_due = 0
    if balance_due < 0:
        refund_due = -balance_due
        balance_due = 0
    has_modifications = len(payments) > 0 and (balance_due > 0 or refund_due > 0)

    email_html = template.render(
        guest_name=booking["guest_name"].split(" ")[0],
        booking_id=booking_id,
        room_img=room_img,
        check_in_day=arr_date.strftime("%A"),
        check_in_date=arr_date.strftime("%b %d, %Y"),
        check_out_day=checkout_date.strftime("%A"),
        check_out_date=checkout_date.strftime("%b %d, %Y"),
        room_label=room_label,
        guest_str=guest_str,
        room_amenities=room_amenities,
        price_per_night=price_per_night,
        nights=booking["nights"],
        total_amount=total_amount,
        branch_name=booking["branch"].title(),
        branch_address=address_html,
        branch_address_inline=address_inline,
        img_prefix=f"{PUBLIC_URL}/api/assets/images/",
        payment_url=f"{PUBLIC_URL}/api/pay/{booking_id}",
        diff_payment_url=f"{PUBLIC_URL}/api/pay/diff/{booking_id}?amount={balance_due}",
        invoice_url=f"{PUBLIC_URL}/api/invoice/{booking_id}",
        payments=payments,
        total_paid=total_paid,
        balance_due=balance_due,
        refund_due=refund_due,
        has_modifications=has_modifications,
    )

    # Save a browser-viewable local copy
    invoices_dir = PROJECT_ROOT / "invoices"
    invoices_dir.mkdir(exist_ok=True)
    local_html = email_html.replace(f"{PUBLIC_URL}/assets/images/", "/assets/images/")
    file_path = invoices_dir / f"invoice_{booking_id}.html"
    with open(file_path, "w", encoding="utf-8") as fh:
        fh.write(local_html)

    # Call Resend API in background thread
    email_status = "Saved locally (no email configured)."
    if email_address and email_address not in ("", "not provided"):
        import asyncio
        sent = await asyncio.to_thread(
            _send_email_resend,
            email_address,
            f"Your NexCell Booking: {booking_id}",
            email_html,
        )
        email_status = (
            f"Sent to {email_address} via Resend."
            if sent
            else "Resend API failed — check server logs. Invoice saved locally."
        )

    return True, f"File: {file_path}. {email_status}"


@mcp.tool()
async def send_invoice(
    booking_id: str,
    email_address: str,
) -> str:
    """Generate and email an HTML invoice for a booking. Works for both LOCKED (pre-payment) and BOOKED (confirmed) states."""
    payload = InvoiceRequest(booking_id=booking_id, email_address=email_address)
    success, message = await _generate_invoice_html(payload.booking_id, payload.email_address)
    if success:
        return f"SUCCESS: Invoice processed. {message}"
    return message


async def api_invoice(request: Request) -> JSONResponse:
    """
    POST /api/invoice  {"booking_id": "NX-...", "email_address": "..."}
    Called directly by voice_server.py — zero LLM tokens consumed.
    """
    try:
        body = await request.json()
        booking_id = body.get("booking_id", "")
        email_address = body.get("email_address", "")
        if not booking_id or not email_address:
            return JSONResponse({"success": False, "error": "booking_id and email_address are required"}, status_code=400)
        success, message = await _generate_invoice_html(booking_id, email_address)
        if success:
            return JSONResponse({"success": True, "file": message, "email": email_address})
        else:
            return JSONResponse({"success": False, "error": message}, status_code=404)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def view_invoice(request: Request) -> HTMLResponse:
    """
    GET /invoice/{booking_id}  — browser-viewable invoice page.
    """
    import os
    booking_id = request.path_params.get("booking_id", "")
    file_path = PROJECT_ROOT / "invoices" / f"invoice_{booking_id}.html"
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse(f"<h2>Invoice {booking_id} not found. Please generate it first.</h2>", status_code=404)

from starlette.routing import Route
invoice_routes = [
    Route("/api/invoice", api_invoice, methods=["POST"]),
    Route("/api/invoice/{booking_id}", view_invoice, methods=["GET"]),
]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="sse", host="127.0.0.1", port=8000)
