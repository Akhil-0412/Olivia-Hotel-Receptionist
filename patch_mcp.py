import re

def patch_mcp():
    with open("src/mcp_server.py", "r", encoding="utf-8") as f:
        content = f.read()
        
    # 1. Replace _INVENTORY and _BOOKINGS with imports
    imports = """from src.database import (
    get_availability, create_booking as db_create_booking, 
    get_booking, modify_booking_room, modify_booking_name, 
    cancel_booking as db_cancel_booking, get_payment_history, INVENTORY_CAPACITY
)"""
    # Regex to match from _INVENTORY up to _BOOKINGS definition
    pattern1 = re.compile(r"# Availability inventory.*_BOOKINGS: dict\[str, dict\] = \{\}", re.DOTALL)
    content = pattern1.sub(imports, content)
    
    # 2. Replace check_availability tool
    new_check = """@mcp.tool()
async def check_availability(
    branch: str,
    arrival_date: str,
    nights: int = 1,
    room_type: str | None = None,
) -> str:
    \"\"\"Check room availability and nightly pricing at a given NexCell branch, date, and optional room type. Returns available units and total cost in GBP.\"\"\"
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
        f"Availability at NexCell {payload.branch.title()} "
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

    return "\\n".join(lines)"""
    pattern2 = re.compile(r"@mcp\.tool\(\)\nasync def check_availability\(.*?return \"\\n\"\.join\(lines\)", re.DOTALL)
    content = pattern2.sub(new_check, content)
    
    # 3. Replace create_booking tool and add new tools
    new_create = """@mcp.tool()
async def create_booking(
    guest_full_name: str,
    branch: str,
    room_type: str,
    arrival_date: str,
    nights: int = 1,
    guest_email: str | None = None,
) -> str:
    \"\"\"Create a reservation. Validates availability, generates a unique HTL reference, and persists the record as LOCKED.\"\"\"
    payload = BookingRequest(
        guest_full_name=guest_full_name,
        branch=branch,
        room_type=room_type,
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
    \"\"\"Look up the details of an existing booking by its reference number.\"\"\"
    booking = get_booking(reference)
    if not booking:
        return f"ERROR: Booking reference '{reference}' not found."
    return f"Booking Details:\\n" + "\\n".join([f"  {k}: {v}" for k, v in booking.items()])

@mcp.tool()
async def modify_booking(reference: str, new_room_type: str = "", new_guest_name: str = "") -> str:
    \"\"\"Modify a booking. Can change room type or guest name. Does not support date changes.\"\"\"
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
            
    return "\\n".join(msgs) if msgs else "No changes requested."

@mcp.tool()
async def cancel_reservation(reference: str) -> str:
    \"\"\"Cancel a booking by reference.\"\"\"
    if db_cancel_booking(reference):
        return f"SUCCESS: Booking '{reference}' cancelled successfully."
    return f"ERROR: Booking '{reference}' not found."
"""
    pattern3 = re.compile(r"@mcp\.tool\(\)\nasync def create_booking\(.*?return confirmation", re.DOTALL)
    content = pattern3.sub(new_create, content)
    
    # 4. Replace invoice generator logic to handle DB and templates
    new_invoice_gen = """async def _generate_invoice_html(booking_id: str, email_address: str) -> tuple[bool, str]:
    \"\"\"
    Core invoice generation logic extracted for reuse.
    Returns (success: bool, message: str)
    If success, the HTML is saved to invoices/<booking_id>.html
    \"\"\"
    import os

    booking = get_booking(booking_id)
    if not booking:
        return False, f"ERROR: Booking reference '{booking_id}' not found."

    arr_date = datetime.date.fromisoformat(booking["arrival_date"])
    checkout_date = datetime.date.fromisoformat(booking["checkout_date"])

    branch_key = booking["branch"].lower()
    room_key = booking["room_type"]
    price_per_night = booking["price_per_night"]
    total_amount = booking["total_cost"]
    
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
        # Choose template based on status
        template_name = "confirmation_invoice_template.html" if booking["status"] == "BOOKED" else "invoice_template.html"
        template = env.get_template(template_name)
    except Exception as e:
        return False, f"ERROR: Could not load template: {e}"

    email_html = template.render(
        guest_name=booking['guest_name'].split(" ")[0],
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
    
    # Also write to local invoices directory
    import os
    invoices_dir = PROJECT_ROOT / "invoices"
    invoices_dir.mkdir(exist_ok=True)
    local_html = email_html.replace("cid:", "/assets/images/")
    local_path = invoices_dir / f"invoice_{booking_id}.html"
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(local_html)

    return True, str(local_path)"""
    
    pattern4 = re.compile(r"async def _generate_invoice_html\(booking_id: str, email_address: str\) -> tuple\[bool, str\]:.*?return True, str\(local_path\)", re.DOTALL)
    content = pattern4.sub(new_invoice_gen, content)

    with open("src/mcp_server.py", "w", encoding="utf-8") as f:
        f.write(content)
        
    print("mcp_server.py patched.")

if __name__ == "__main__":
    patch_mcp()
