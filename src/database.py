import sqlite3
import random
import datetime
import uuid
import json
from pathlib import Path
from typing import Optional

import os

PROJECT_ROOT = Path(__file__).parent.parent

# On Hugging Face Spaces, /data/ is the persistent volume that survives rebuilds.
# Locally, fall back to the project data/ directory.
if os.environ.get("SPACE_HOST") or os.environ.get("SPACE_ID"):
    _data_dir = Path("/data")
    _data_dir.mkdir(parents=True, exist_ok=True)
    DB_PATH = _data_dir / "hotel.db"
else:
    DB_PATH = PROJECT_ROOT / "data" / "nexcell.db"


ROOM_TYPE_CODES = {
    "standard_twin": "ST",
    "deluxe_double": "DXD",
    "executive_suite": "PS",
}
BRANCH_CODES = {
    "london": "LND",
    "manchester": "MAN",
    "edinburgh": "EDN",
}

# Base inventory info for calculation
INVENTORY_CAPACITY = {
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

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    # Make sure the data dir exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # bookings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            reference TEXT PRIMARY KEY,
            guest_name TEXT NOT NULL,
            guest_email TEXT,
            branch TEXT NOT NULL,
            room_type TEXT NOT NULL,
            arrival_date TEXT NOT NULL,
            checkout_date TEXT NOT NULL,
            nights INTEGER NOT NULL,
            price_per_night INTEGER NOT NULL,
            total_cost INTEGER NOT NULL,
            status TEXT NOT NULL,
            locked_at TEXT,
            paid_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    
    # payments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            payment_id TEXT PRIMARY KEY,
            booking_reference TEXT NOT NULL,
            amount_gbp INTEGER NOT NULL,
            type TEXT NOT NULL,
            status TEXT NOT NULL,
            mock_card_last4 TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(booking_reference) REFERENCES bookings(reference)
        )
    ''')
    
    # booking_history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS booking_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_reference TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(booking_reference) REFERENCES bookings(reference)
        )
    ''')
    
    conn.commit()
    conn.close()

def generate_reference(room_type: str, branch: str, status: str = "LCK") -> str:
    room_code = ROOM_TYPE_CODES.get(room_type, "UNK")
    branch_code = BRANCH_CODES.get(branch.lower(), "UNK")
    chars_needed = max(0, 5 - len(room_code))
    unique_part = ''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ23456789', k=chars_needed))
    identity = f"{room_code}{unique_part}"[:5]
    return f"HTL-{status}-{identity}-{branch_code}"

def update_reference_status(old_ref: str, new_status: str) -> str:
    """Changes HTL-LCK-ST123-LND to HTL-BKD-ST123-LND"""
    parts = old_ref.split("-")
    if len(parts) == 4:
        parts[1] = new_status
        return "-".join(parts)
    return old_ref

def update_reference_room_type(old_ref: str, new_room_type: str) -> str:
    """Changes HTL-BKD-ST4Q9-LND to HTL-BKD-DXD4Q-LND"""
    parts = old_ref.split("-")
    if len(parts) != 4:
        return old_ref
        
    old_identity = parts[2]
    new_room_code = ROOM_TYPE_CODES.get(new_room_type, "UNK")
    
    # Keep the alphanumeric tail, adjust to 5 chars
    unique_tail = old_identity[len(old_identity) - (5 - len(new_room_code)):] if 5 > len(new_room_code) else ""
    # If tail is too short, pad with random char
    while len(new_room_code) + len(unique_tail) < 5:
        unique_tail += random.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789')
        
    new_identity = f"{new_room_code}{unique_tail[:5-len(new_room_code)]}"
    parts[2] = new_identity
    return "-".join(parts)

def get_availability(branch: str, check_date: str) -> dict:
    branch_key = branch.lower()
    if branch_key not in INVENTORY_CAPACITY:
        return {}
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    date_inventory = {}
    for rt, info in INVENTORY_CAPACITY[branch_key].items():
        # Count overlapping active bookings (LOCKED or BOOKED)
        cursor.execute('''
            SELECT COUNT(*) as booked_count FROM bookings
            WHERE branch = ? AND room_type = ? 
            AND status IN ('LOCKED', 'BOOKED')
            AND arrival_date <= ? AND checkout_date > ?
        ''', (branch_key, rt, check_date, check_date))
        
        row = cursor.fetchone()
        booked_count = row['booked_count'] if row else 0
        date_inventory[rt] = {
            "units": max(0, info["capacity"] - booked_count),
            "price_gbp": info["price_gbp"]
        }
        
    conn.close()
    return date_inventory

def create_booking(guest_name: str, guest_email: str, branch: str, room_type: str, 
                   arrival_date: str, nights: int, price_per_night: int, total_cost: int) -> str:
    reference = generate_reference(room_type, branch, "LCK")
    now = datetime.datetime.utcnow().isoformat()
    arrival = datetime.date.fromisoformat(arrival_date)
    checkout = (arrival + datetime.timedelta(days=nights)).isoformat()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO bookings (
            reference, guest_name, guest_email, branch, room_type,
            arrival_date, checkout_date, nights, price_per_night, total_cost,
            status, locked_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        reference, guest_name, guest_email, branch.lower(), room_type,
        arrival_date, checkout, nights, price_per_night, total_cost,
        "LOCKED", now, now, now
    ))
    
    cursor.execute('''
        INSERT INTO booking_history (booking_reference, action, details, created_at)
        VALUES (?, ?, ?, ?)
    ''', (reference, "CREATED", json.dumps({"status": "LOCKED"}), now))
    
    conn.commit()
    conn.close()
    return reference

def get_booking(reference: str) -> Optional[dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM bookings WHERE reference = ?', (reference,))
    row = cursor.fetchone()

    # Fallback 1: If it's a LCK/BKD status change, the reference might have flipped
    if not row and "-LCK-" in reference:
        cursor.execute('SELECT * FROM bookings WHERE reference = ?', (reference.replace("-LCK-", "-BKD-"),))
        row = cursor.fetchone()
    elif not row and "-BKD-" in reference:
        cursor.execute('SELECT * FROM bookings WHERE reference = ?', (reference.replace("-BKD-", "-LCK-"),))
        row = cursor.fetchone()

    # Fallback 2: Check booking_history for 'old_reference' (e.g. room modifications)
    if not row:
        cursor.execute('''
            SELECT b.* 
            FROM bookings b
            JOIN booking_history h ON b.reference = h.booking_reference
            WHERE h.details LIKE ?
        ''', (f'%"{reference}"%',))
        row = cursor.fetchone()

    conn.close()
    if row:
        return dict(row)
    return None

def update_booking_status(reference: str, new_status: str) -> Optional[str]:
    booking = get_booking(reference)
    if not booking:
        return None
        
    new_reference = update_reference_status(reference, "BKD" if new_status == "BOOKED" else "LCK")
    now = datetime.datetime.utcnow().isoformat()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE bookings 
        SET reference = ?, status = ?, updated_at = ?
        WHERE reference = ?
    ''', (new_reference, new_status, now, reference))
    
    # Also update history foreign keys if reference changed
    if new_reference != reference:
        cursor.execute('''
            UPDATE booking_history SET booking_reference = ? WHERE booking_reference = ?
        ''', (new_reference, reference))
        cursor.execute('''
            UPDATE payments SET booking_reference = ? WHERE booking_reference = ?
        ''', (new_reference, reference))
    
    cursor.execute('''
        INSERT INTO booking_history (booking_reference, action, details, created_at)
        VALUES (?, ?, ?, ?)
    ''', (new_reference, "STATUS_CHANGED", json.dumps({"old": booking["status"], "new": new_status}), now))
    
    conn.commit()
    conn.close()
    return new_reference

def modify_booking_room(reference: str, new_room_type: str) -> dict:
    """Modifies a booking's room type. Returns dict with new details."""
    booking = get_booking(reference)
    if not booking:
        raise ValueError("Booking not found")
        
    branch = booking["branch"]
    nights = booking["nights"]
    old_room = booking["room_type"]
    
    if new_room_type not in INVENTORY_CAPACITY.get(branch, {}):
        raise ValueError(f"Invalid room type {new_room_type} for branch {branch}")
        
    new_price = INVENTORY_CAPACITY[branch][new_room_type]["price_gbp"]
    new_total = new_price * nights
    price_diff = new_total - booking["total_cost"]
    
    new_reference = update_reference_room_type(reference, new_room_type)
    now = datetime.datetime.utcnow().isoformat()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE bookings 
        SET reference = ?, room_type = ?, price_per_night = ?, total_cost = ?, updated_at = ?
        WHERE reference = ?
    ''', (new_reference, new_room_type, new_price, new_total, now, reference))
    
    if new_reference != reference:
        cursor.execute('UPDATE booking_history SET booking_reference = ? WHERE booking_reference = ?', (new_reference, reference))
        cursor.execute('UPDATE payments SET booking_reference = ? WHERE booking_reference = ?', (new_reference, reference))
        
    cursor.execute('''
        INSERT INTO booking_history (booking_reference, action, details, created_at)
        VALUES (?, ?, ?, ?)
    ''', (new_reference, "ROOM_CHANGED", json.dumps({
        "old_room": old_room, "new_room": new_room_type, 
        "old_total": booking["total_cost"], "new_total": new_total,
        "diff": price_diff
    }), now))
    
    conn.commit()
    conn.close()
    
    return {
        "new_reference": new_reference,
        "price_difference": price_diff,
        "new_total": new_total
    }

def modify_booking_name(reference: str, new_name: str) -> bool:
    booking = get_booking(reference)
    if not booking:
        return False
        
    now = datetime.datetime.utcnow().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE bookings SET guest_name = ?, updated_at = ? WHERE reference = ?
    ''', (new_name, now, reference))
    
    cursor.execute('''
        INSERT INTO booking_history (booking_reference, action, details, created_at)
        VALUES (?, ?, ?, ?)
    ''', (reference, "NAME_CHANGED", json.dumps({"old": booking["guest_name"], "new": new_name}), now))
    
    conn.commit()
    conn.close()
    return True

def cancel_booking(reference: str) -> bool:
    booking = get_booking(reference)
    if not booking:
        return False
        
    now = datetime.datetime.utcnow().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE bookings SET status = 'CANCELLED', updated_at = ? WHERE reference = ?
    ''', (now, reference))
    
    cursor.execute('''
        INSERT INTO booking_history (booking_reference, action, details, created_at)
        VALUES (?, ?, ?, ?)
    ''', (reference, "CANCELLED", json.dumps({"reason": "User requested cancellation"}), now))
    
    conn.commit()
    conn.close()
    return True

def expire_stale_locks() -> int:
    now = datetime.datetime.utcnow()
    threshold = (now - datetime.timedelta(hours=24)).isoformat()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT reference FROM bookings 
        WHERE status = 'LOCKED' AND locked_at < ?
    ''', (threshold,))
    
    expired_refs = [row['reference'] for row in cursor.fetchall()]
    
    now_iso = now.isoformat()
    for ref in expired_refs:
        cursor.execute('''
            UPDATE bookings SET status = 'EXPIRED', updated_at = ? WHERE reference = ?
        ''', (now_iso, ref))
        cursor.execute('''
            INSERT INTO booking_history (booking_reference, action, details, created_at)
            VALUES (?, ?, ?, ?)
        ''', (ref, "EXPIRED", json.dumps({"reason": "24h lock expired"}), now_iso))
        
    conn.commit()
    conn.close()
    return len(expired_refs)

def record_payment(booking_reference: str, amount_gbp: int, payment_type: str, mock_card_last4: str) -> str:
    payment_id = f"pay_{uuid.uuid4().hex}"
    now = datetime.datetime.utcnow().isoformat()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO payments (payment_id, booking_reference, amount_gbp, type, status, mock_card_last4, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (payment_id, booking_reference, amount_gbp, payment_type, "COMPLETED", mock_card_last4, now))
    
    # If this is a full payment, update booking paid_at
    if payment_type == "FULL":
        cursor.execute('''
            UPDATE bookings SET paid_at = ?, updated_at = ? WHERE reference = ?
        ''', (now, now, booking_reference))
        
    cursor.execute('''
        INSERT INTO booking_history (booking_reference, action, details, created_at)
        VALUES (?, ?, ?, ?)
    ''', (booking_reference, "PAYMENT_RECORDED", json.dumps({
        "payment_id": payment_id, "amount": amount_gbp, "type": payment_type
    }), now))
    
    conn.commit()
    conn.close()
    return payment_id

def get_payment_history(reference: str) -> list[dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM payments WHERE booking_reference = ? ORDER BY created_at ASC', (reference,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
