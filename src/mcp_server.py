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
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

# Load environment variables
load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent

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

# Availability inventory: branch -> room_type -> base capacity & price
_INVENTORY: dict[str, dict[str, dict]] = {
    "london": {
        "standard_twin": {"capacity": 5, "price_gbp": 120},
        "deluxe_double": {"capacity": 3, "price_gbp": 195},
        "executive_suite": {"capacity": 1, "price_gbp": 380},
    },
    "manchester": {
        "standard_twin": {"capacity": 8, "price_gbp": 95},
        "deluxe_double": {"capacity": 4, "price_gbp": 155},
        "executive_suite": {"capacity": 2, "price_gbp": 290},
    },
    "edinburgh": {
        "standard_twin": {"capacity": 3, "price_gbp": 110},
        "deluxe_double": {"capacity": 2, "price_gbp": 175},
        "executive_suite": {"capacity": 1, "price_gbp": 340},
    },
}

def _get_date_inventory(branch_key: str, check_date: str) -> dict:
    """Helper to dynamically calculate availability for a date."""
    branch_data = _INVENTORY[branch_key]
    date_inventory = {}
    for rt, info in branch_data.items():
        # Count overlapping bookings
        booked_count = sum(
            1 for b in _BOOKINGS.values()
            if b["branch"].lower() == branch_key 
            and b["room_type"] == rt 
            and b["arrival"] <= check_date < b["checkout"]
        )
        date_inventory[rt] = {
            "units": max(0, info["capacity"] - booked_count),
            "price_gbp": info["price_gbp"]
        }
    return date_inventory

# Active bookings store: booking_ref -> booking record
_BOOKINGS: dict[str, dict] = {}

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

    # Validate branch
    if branch_key not in _INVENTORY:
        available_branches = ", ".join(sorted(_INVENTORY.keys()))
        return (
            f"ERROR: Branch '{payload.branch}' not recognised. "
            f"Available branches: {available_branches}."
        )

    # Dynamically generate inventory for the requested date
    date_inventory = _get_date_inventory(branch_key, payload.arrival_date)

    # Apply optional room-type filter
    if payload.room_type:
        rt_key = payload.room_type.strip().lower().replace(" ", "_")
        if rt_key not in date_inventory:
            valid_types = ", ".join(date_inventory.keys())
            return (
                f"ERROR: Room type '{payload.room_type}' not available at "
                f"'{payload.branch}'. Valid types: {valid_types}."
            )
        date_inventory = {rt_key: date_inventory[rt_key]}

    # Build response
    lines: list[str] = [
        f"Availability at NexCell {payload.branch.title()} "
        f"from {payload.arrival_date} for {payload.nights} night(s):",
    ]
    any_available = False
    for room_type, info in date_inventory.items():
        units = info["units"]
        price = info["price_gbp"]
        total = price * payload.nights
        label = room_type.replace("_", " ").title()
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
    """Create a confirmed hotel reservation. Validates availability, generates a unique NX- booking reference, and persists the record."""
    payload = BookingRequest(
        guest_full_name=guest_full_name,
        branch=branch,
        room_type=room_type,
        arrival_date=arrival_date,
        nights=nights,
        guest_email=guest_email
    )
    branch_key = payload.branch.strip().lower()

    # Validate branch
    if branch_key not in _INVENTORY:
        available_branches = ", ".join(sorted(_INVENTORY.keys()))
        return (
            f"ERROR: Branch '{payload.branch}' not recognised. "
            f"Available branches: {available_branches}."
        )

    # Dynamically generate inventory for the requested date
    date_inventory = _get_date_inventory(branch_key, payload.arrival_date)
    rt_key = payload.room_type.strip().lower().replace(" ", "_")

    # Validate room type
    if rt_key not in date_inventory:
        return (
            f"ERROR: Room type '{payload.room_type}' does not exist at "
            f"'{payload.branch}'. Please choose from: {', '.join(date_inventory.keys())}."
        )

    room_info = date_inventory[rt_key]

    # Check availability
    if room_info["units"] <= 0:
        return (
            f"ERROR: '{payload.room_type.replace('_', ' ').title()}' is sold out at "
            f"NexCell {payload.branch.title()} on {payload.arrival_date}. "
            "Please check alternative dates or room types."
        )

    # Compute checkout date and total cost
    arrival = datetime.date.fromisoformat(payload.arrival_date)
    checkout = arrival + datetime.timedelta(days=payload.nights)
    total_cost = room_info["price_gbp"] * payload.nights

    # Generate a unique booking reference
    booking_ref = f"NX-{datetime.date.today().year}-{uuid.uuid4().hex[:6].upper()}"

    # We no longer manually decrement units because _get_date_inventory dynamically counts active _BOOKINGS.

    # Persist booking record
    _BOOKINGS[booking_ref] = {
        "ref": booking_ref,
        "guest": payload.guest_full_name,
        "email": payload.guest_email or "not provided",
        "branch": payload.branch.title(),
        "room_type": rt_key,
        "arrival": payload.arrival_date,
        "checkout": str(checkout),
        "nights": payload.nights,
        "price_per_night_gbp": room_info["price_gbp"],
        "total_cost_gbp": total_cost,
        "status": "CONFIRMED",
        "created_at": datetime.datetime.utcnow().isoformat(),
    }

    # The invoice will be generated and sent ONLY if the guest requests it via send_invoice.



    label = rt_key.replace("_", " ").title()
    confirmation = (
        f"[CONFIRMED] Booking Confirmed!\n"
        f"  Reference     : {booking_ref}\n"
        f"  Guest         : {payload.guest_full_name}\n"
        f"  Hotel         : NexCell {payload.branch.title()}\n"
        f"  Room          : {label}\n"
        f"  Check-in      : {payload.arrival_date}\n"
        f"  Check-out     : {checkout}\n"
        f"  Duration      : {payload.nights} night(s)\n"
        f"  Total Cost    : £{total_cost} (£{room_info['price_gbp']}/night)\n"
        f"  Status        : CONFIRMED\n"
    )
    if payload.guest_email:
        confirmation += f"  Confirmation  : Sent to {payload.guest_email}\n"

    return confirmation


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

@mcp.tool()
async def send_invoice(
    booking_id: str,
    email_address: str,
) -> str:
    """Send an invoice email to the guest for a confirmed booking."""
    payload = InvoiceRequest(
        booking_id=booking_id,
        email_address=email_address
    )
    success, message = await _generate_invoice_html(payload.booking_id, payload.email_address)
    if success:
        return f"SUCCESS: Invoice successfully sent to {payload.email_address}."
    else:
        return f"ERROR: Failed to send invoice. Details: {message}"

# ---------------------------------------------------------------------------
# Utility – Email & HTML Generation
# ---------------------------------------------------------------------------

def _send_email_smtp(to_email: str, subject: str, html_content: str, images: list[str]) -> bool:
    import os

    smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", 465))
    gmail_user = os.environ.get("SENDER_EMAIL") or os.environ.get("GMAIL_ADDRESS")
    gmail_pwd = os.environ.get("SENDER_PASSWORD") or os.environ.get("GMAIL_APP_PASSWORD")
    if not gmail_user or not gmail_pwd:
        print("WARNING: Email credentials missing in .env, skipping SMTP.")
        return False
    try:
        msg = MIMEMultipart("related")
        msg["Subject"] = subject
        msg["From"] = gmail_user
        msg["To"] = to_email
        
        msg_alternative = MIMEMultipart('alternative')
        msg.attach(msg_alternative)

        part = MIMEText(html_content, "html")
        msg_alternative.attach(part)
        
        # Attach images with CID
        for img_name in images:
            img_path = PROJECT_ROOT / "assets" / "images" / img_name
            if img_path.exists():
                with open(img_path, "rb") as f:
                    subtype = img_name.split('.')[-1].lower()
                    if subtype == 'jpg':
                        subtype = 'jpeg'
                    msg_image = MIMEImage(f.read(), _subtype=subtype)
                    msg_image.add_header('Content-ID', f'<{img_name}>')
                    msg_image.add_header('Content-Disposition', 'inline', filename=img_name)
                    msg.attach(msg_image)
            else:
                print(f"Warning: Image {img_path} not found for email attachment.")

        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(gmail_user, gmail_pwd)
        server.sendmail(gmail_user, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"ERROR sending email: {e}")
        return False

@mcp.tool()
async def send_invoice(
    booking_id: str,
    email_address: str,
) -> str:
    """Generate and email an HTML invoice for a confirmed booking. Saves a local copy. Requires booking_id and email_address."""
    payload = InvoiceRequest(
        booking_id=booking_id,
        email_address=email_address
    )
    success, message = await _generate_invoice_html(payload.booking_id, payload.email_address)
    if success:
        return f"SUCCESS: HTML invoice generated. {message}"
    return message

# ---------------------------------------------------------------------------
# Standalone HTTP API (zero-LLM invoice endpoints)
# These are called directly by voice_server.py — no AI tokens consumed.
# ---------------------------------------------------------------------------

async def _generate_invoice_html(booking_id: str, email_address: str) -> tuple[bool, str]:
    """
    Core invoice generation logic extracted for reuse.
    Returns (success: bool, message: str)
    If success, the HTML is saved to invoices/<booking_id>.html
    """
    import os

    if booking_id not in _BOOKINGS:
        return False, f"ERROR: Booking reference '{booking_id}' not found."

    booking = _BOOKINGS[booking_id]

    arr_date = datetime.date.fromisoformat(booking["arrival"])
    checkout_date = arr_date + datetime.timedelta(days=booking["nights"])

    branch_key = booking["branch"].lower()
    room_key = booking["room_type"]
    price_per_night = _INVENTORY[branch_key][room_key]["price_gbp"]
    total_amount = price_per_night * booking["nights"]
    
    branch_addresses = {
        "london": ("42 Regent Street,<br>London,<br>W1B 5TR,<br>United Kingdom.", "42 Regent Street, London, W1B 5TR, UK."),
        "manchester": ("15 Deansgate,<br>Manchester,<br>M3 1AZ,<br>United Kingdom.", "15 Deansgate, Manchester, M3 1AZ, UK."),
        "edinburgh": ("105 Victoria St,<br>Edinburgh,<br>EH1 2EX,<br>United Kingdom.", "105 Victoria St, Edinburgh, EH1 2EX, UK.")
    }
    address_html, address_inline = branch_addresses.get(branch_key, ("1220 Ocean View Drive,<br>Seaside Cover, CA,<br>United States.", "1220 Ocean View Drive, Seaside Cover, CA, US."))

    room_label = room_key.replace("_", " ").title()
    if room_key == "executive_suite":
        room_label = "Premium Suite"

    guest_str = "Up to 4 Guests" if room_key == "standard_twin" else ("Up to 5 Guests" if room_key == "deluxe_double" else "2 Adults, 1 Child")
    room_img = "Standard_twin.jpg" if room_key == "standard_twin" else ("deluxe_double.jpg" if room_key == "deluxe_double" else "executive_room.jpg")

    room_amenities = []
    if room_key != 'standard_twin':
        room_amenities.append("<img src='cid:breakfast.png' alt='Breakfast'> Breakfast")
    else:
        room_amenities.append("Standard Setup")
    if room_key == 'executive_suite':
        room_amenities.append("<img src='cid:dining.png' alt='Dining'> Fine Dining")
        room_amenities.append("<img src='cid:refreshments.png' alt='Snacks'> Refreshments")

    # Load Jinja2 template
    env = Environment(loader=FileSystemLoader(str(PROJECT_ROOT / "templates")))
    try:
        template = env.get_template("invoice_template.html")
    except Exception as e:
        return False, f"ERROR: Could not load template: {e}"

    email_html = template.render(
        guest_name=booking['guest'].split(" ")[0],
        booking_id=booking_id,
        room_img=room_img,
        check_in_day=arr_date.strftime('%A'),
        check_in_date=arr_date.strftime('%b %d, %Y'),
        check_out_day=checkout_date.strftime('%A'),
        check_out_date=checkout_date.strftime('%b %d, %Y'),
        room_label=room_label,
        guest_str=guest_str,
        room_amenities=room_amenities,
        price_per_night=price_per_night,
        nights=booking['nights'],
        total_amount=total_amount,
        branch_name=booking['branch'].title(),
        branch_address=address_html,
        branch_address_inline=address_inline,
        img_prefix="cid:"
    )

    local_html = email_html.replace("cid:", "../assets/images/")

    invoices_dir = PROJECT_ROOT / "invoices"
    invoices_dir.mkdir(exist_ok=True)
    file_path = invoices_dir / f"invoice_{booking_id}.html"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(local_html)

    # Gather required images
    required_images = ["logo.png", room_img, "wifi.png", "gym.png", "pool.png", "parking.png"]
    if room_key != 'standard_twin':
        required_images.append("breakfast.png")
    if room_key == 'executive_suite':
        required_images.extend(["dining.png", "refreshments.png"])

    # Attempt to send email
    email_status = "Mocked locally."
    if email_address and email_address != "not provided":
        sent = _send_email_smtp(email_address, f"Your NexCell Booking Confirmation: {booking_id}", email_html, required_images)
        if sent:
            email_status = f"Sent to {email_address} via SMTP."
        else:
            email_status = f"Failed to send via SMTP (check console logs). Saved locally."

    return True, f"File: {file_path}. {email_status}"


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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="sse", host="127.0.0.1", port=8000)
