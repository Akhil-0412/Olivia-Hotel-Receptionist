"""
payment_portal.py
=================
Mock Stripe-style payment portal mounted into the FastAPI app.
Handles:
  GET  /pay/{reference}           → Payment page (with 24-hour timer)
  POST /pay/{reference}           → Process full payment
  GET  /pay/success/{reference}   → Success confirmation page
  GET  /pay/diff/{reference}      → Upgrade/downgrade difference payment page
  POST /pay/diff/{reference}      → Process difference payment
"""
from __future__ import annotations

import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.routing import Route

from src.database import get_booking, record_payment, update_booking_status

PROJECT_ROOT = Path(__file__).parent.parent
_jinja_env = Environment(loader=FileSystemLoader(str(PROJECT_ROOT / "templates")))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _render(template_name: str, **ctx) -> str:
    return _jinja_env.get_template(template_name).render(**ctx)


def _time_left(booking: dict) -> int:
    """Returns seconds remaining on the 24-hour lock, minimum 0."""
    locked_at = datetime.datetime.fromisoformat(booking["locked_at"])
    expiry = locked_at + datetime.timedelta(hours=24)
    delta = (expiry - datetime.datetime.utcnow()).total_seconds()
    return max(0, int(delta))


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

async def view_payment_page(request: Request) -> HTMLResponse:
    reference = request.path_params.get("reference", "")
    booking = get_booking(reference)

    if not booking:
        return HTMLResponse("<h2>Booking not found.</h2>", status_code=404)
    if booking["status"] == "EXPIRED":
        return HTMLResponse(
            "<h2>This booking lock has expired. Please make a new booking.</h2>",
            status_code=410,
        )
    if booking["status"] == "BOOKED":
        return HTMLResponse(
            f"<h2>Booking {booking['reference']} is already confirmed. "
            f"Check your email for the confirmation invoice.</h2>",
            status_code=200,
        )
    if booking["status"] == "CANCELLED":
        return HTMLResponse("<h2>This booking has been cancelled.</h2>", status_code=410)

    html = _render(
        "payment_page.html",
        booking=booking,
        time_left_seconds=_time_left(booking),
        is_diff=False,
        diff_amount=0,
    )
    return HTMLResponse(html)


async def process_payment(request: Request) -> RedirectResponse:
    reference = request.path_params.get("reference", "")
    booking = get_booking(reference)

    if not booking or booking["status"] != "LOCKED":
        return RedirectResponse(url=f"/pay/{reference}?error=invalid_state", status_code=303)

    form = await request.form()
    card_number = str(form.get("card_number", "0000"))
    mock_last4 = card_number[-4:] if len(card_number) >= 4 else "0000"

    # 1. Record payment
    record_payment(reference, booking["total_cost"], "FULL", mock_last4)
    # 2. Flip status LOCKED → BOOKED (also updates the reference prefix to BKD)
    new_reference = update_booking_status(reference, "BOOKED")

    # 3. Fire and forget the confirmation invoice generation
    import asyncio
    import httpx
    async def send_invoice():
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post("http://127.0.0.1:7860/api/invoice", json={
                    "booking_id": new_reference,
                    "email_address": booking["guest_email"]
                })
        except Exception:
            pass
    asyncio.create_task(send_invoice())

    return RedirectResponse(url=f"/pay/success/{new_reference}", status_code=303)


async def view_payment_success(request: Request) -> HTMLResponse:
    reference = request.path_params.get("reference", "")
    booking = get_booking(reference)

    if not booking:
        return HTMLResponse("<h2>Booking not found.</h2>", status_code=404)

    html = _render("payment_success.html", booking=booking)
    return HTMLResponse(html)


async def view_diff_payment(request: Request) -> HTMLResponse:
    reference = request.path_params.get("reference", "")
    booking = get_booking(reference)

    if not booking:
        return HTMLResponse("<h2>Booking not found.</h2>", status_code=404)

    try:
        diff_amount = int(str(request.query_params.get("amount", 0)))
    except ValueError:
        diff_amount = 0

    if diff_amount == 0:
        return HTMLResponse("<h2>No difference to pay for this modification.</h2>")

    html = _render(
        "payment_page.html",
        booking=booking,
        time_left_seconds=None,  # Not a locked booking — no timer shown
        is_diff=True,
        diff_amount=diff_amount,
    )
    return HTMLResponse(html)


async def process_diff_payment(request: Request) -> RedirectResponse:
    reference = request.path_params.get("reference", "")
    booking = get_booking(reference)

    if not booking:
        return RedirectResponse(url=f"/pay/diff/{reference}?error=not_found", status_code=303)

    form = await request.form()
    card_number = str(form.get("card_number", "0000"))
    mock_last4 = card_number[-4:] if len(card_number) >= 4 else "0000"

    try:
        diff_amount = int(str(form.get("diff_amount", 0)))
    except (ValueError, TypeError):
        diff_amount = 0

    payment_type = "UPGRADE_DIFF" if diff_amount > 0 else "REFUND"
    record_payment(reference, abs(diff_amount), payment_type, mock_last4)

    # Fire and forget the updated confirmation invoice generation
    import asyncio
    import httpx
    async def send_invoice():
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post("http://127.0.0.1:7860/api/invoice", json={
                    "booking_id": reference,
                    "email_address": booking["guest_email"]
                })
        except Exception:
            pass
    asyncio.create_task(send_invoice())

    return RedirectResponse(url=f"/pay/success/{reference}", status_code=303)


# ---------------------------------------------------------------------------
# Route table — order matters: specific paths before parameterised ones
# ---------------------------------------------------------------------------

payment_routes = [
    Route("/pay/success/{reference}", view_payment_success, methods=["GET"]),
    Route("/pay/diff/{reference}",    view_diff_payment,    methods=["GET"]),
    Route("/pay/diff/{reference}",    process_diff_payment, methods=["POST"]),
    Route("/pay/{reference}",         view_payment_page,    methods=["GET"]),
    Route("/pay/{reference}",         process_payment,      methods=["POST"]),
]
