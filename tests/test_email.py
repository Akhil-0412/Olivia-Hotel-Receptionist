import asyncio
import os
from dotenv import load_dotenv

# Load env variables first
load_dotenv()

import mcp_server

async def run_test():
    # Insert a fake booking to test the invoice generation and email
    test_booking_id = "NX-TEST-000"
    mcp_server._BOOKINGS[test_booking_id] = {
        "ref": test_booking_id,
        "guest": "Akhileshwar Test",
        "email": "akhileshwar008@gmail.com",
        "branch": "London",
        "room_type": "standard_twin",
        "arrival": "2026-07-20",
        "checkout": "2026-07-22",
        "nights": 2,
        "price_per_night_gbp": 120,
        "total_cost_gbp": 240,
        "status": "CONFIRMED",
        "created_at": "2026-07-10T12:00:00Z"
    }
    
    print("Generating and sending invoice...")
    success, message = await mcp_server._generate_invoice_html(test_booking_id, "akhileshwar008@gmail.com")
    
    print(f"\nResult:")
    print(f"Success: {success}")
    print(f"Message: {message}")

if __name__ == "__main__":
    asyncio.run(run_test())
