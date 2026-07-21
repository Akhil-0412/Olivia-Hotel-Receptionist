"""
app_gradio.py
=============
NexCell Hotel Receptionist — Hugging Face Spaces entry point

Architecture:
  - FastMCP server runs in a background asyncio thread (port 8000)
  - LiveKit voice worker runs as a subprocess (registers as 'nexcell-receptionist')
  - Gradio UI provides a beautiful frontend for guests to connect via LiveKit
  - @spaces.GPU decorator available for on-demand local Whisper transcription

HF Space: https://huggingface.co/spaces/Akhil-008/Olivia-Hotel-Receptionist
"""

from __future__ import annotations

import asyncio
import datetime
import os
import subprocess
import sys
import threading
import time

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Background services — MCP + Voice Worker
# ---------------------------------------------------------------------------

_services_started = False

def _run_mcp_in_thread():
    """Run FastMCP SSE server in a dedicated asyncio event loop thread."""
    from src.mcp_server import mcp
    from src.database import init_db
    from src.lock_scheduler import lock_expiry_daemon

    async def _main():
        init_db()
        print("[HF App] SQLite DB initialised.", flush=True)
        asyncio.create_task(lock_expiry_daemon())
        print("[HF App] Lock expiry daemon started.", flush=True)
        await mcp.run_async(transport="sse", host="127.0.0.1", port=8000)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_main())


def start_background_services():
    global _services_started
    if _services_started:
        return
    _services_started = True

    # 1. MCP server in a background thread
    t = threading.Thread(target=_run_mcp_in_thread, daemon=True)
    t.start()
    print("[HF App] MCP server thread started.", flush=True)

    # 2. Wait briefly for MCP to boot before the voice worker tries to connect
    time.sleep(3)

    # 3. LiveKit voice worker — only if credentials are set
    if os.environ.get("LIVEKIT_URL"):
        print("[HF App] Starting LiveKit voice worker...", flush=True)
        subprocess.Popen(
            [sys.executable, "-m", "src.voice_server", "start"],
            stdout=sys.stdout,
            stderr=sys.stderr,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        print("[HF App] Voice worker launched.", flush=True)
    else:
        print("[HF App] LIVEKIT_URL not set — voice worker skipped.", flush=True)


# Start services before Gradio UI loads
start_background_services()

# ---------------------------------------------------------------------------
# ZeroGPU — on-demand local Whisper transcription
# ---------------------------------------------------------------------------

try:
    import spaces
    HAS_ZEROGPU = True
except ImportError:
    HAS_ZEROGPU = False

if HAS_ZEROGPU:
    @spaces.GPU(duration=60)
    def transcribe_audio_gpu(audio_path: str) -> str:
        """Transcribe audio locally using Whisper on ZeroGPU (A10G)."""
        import torch
        import whisper  # openai-whisper
        print("[ZeroGPU] Loading Whisper base model on GPU...", flush=True)
        model = whisper.load_model("base", device="cuda" if torch.cuda.is_available() else "cpu")
        result = model.transcribe(audio_path, language="en")
        return result["text"].strip()
else:
    def transcribe_audio_gpu(audio_path: str) -> str:  # type: ignore
        return "ZeroGPU not available in this environment."


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------

import gradio as gr

LIVEKIT_URL = os.environ.get("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY", "")

PLAYGROUND_URL = (
    f"https://agents-playground.livekit.io/#"
    f"?liveKitUrl={LIVEKIT_URL}"
    f"&token=PASTE_TOKEN_HERE"
    if LIVEKIT_URL
    else "https://agents-playground.livekit.io/"
)

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@300;400;500;600;700&display=swap');

* { box-sizing: border-box; }

body, .gradio-container {
    font-family: 'Inter', sans-serif !important;
    background: #060b13 !important;
    color: #e2e8f0 !important;
}

.hero-section {
    background: linear-gradient(135deg, #0a1424 0%, #060b13 50%, #0d1e36 100%);
    border: 1px solid rgba(56,189,248,0.2);
    border-radius: 20px;
    padding: 48px;
    text-align: center;
    margin-bottom: 24px;
    position: relative;
    overflow: hidden;
}

.hero-section::before {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(ellipse at center, rgba(56,189,248,0.06) 0%, transparent 70%);
    pointer-events: none;
}

.hero-title {
    font-family: 'Outfit', sans-serif;
    font-size: 3.2rem;
    font-weight: 700;
    background: linear-gradient(135deg, #38bdf8, #818cf8, #e2e8f0);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 8px 0;
    letter-spacing: -0.02em;
}

.hero-subtitle {
    font-size: 1.15rem;
    color: #94a3b8;
    margin: 0 0 32px 0;
    font-weight: 300;
}

.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(56,189,248,0.1);
    border: 1px solid rgba(56,189,248,0.3);
    border-radius: 999px;
    padding: 6px 16px;
    font-size: 0.85rem;
    color: #38bdf8;
    font-weight: 500;
}

.status-dot {
    width: 8px;
    height: 8px;
    background: #38bdf8;
    border-radius: 50%;
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
}

.call-button {
    display: inline-block;
    margin-top: 24px;
    padding: 16px 40px;
    background: linear-gradient(135deg, #0284c7, #6366f1);
    color: white !important;
    font-size: 1.1rem;
    font-weight: 600;
    border-radius: 12px;
    text-decoration: none !important;
    border: none;
    cursor: pointer;
    transition: all 0.3s ease;
    box-shadow: 0 0 30px rgba(56,189,248,0.3);
}

.call-button:hover {
    transform: translateY(-2px);
    box-shadow: 0 0 50px rgba(99,102,241,0.6);
}

.features-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-bottom: 24px;
}

.feature-card {
    background: rgba(10,20,38,0.6);
    border: 1px solid rgba(56,189,248,0.15);
    border-radius: 16px;
    padding: 24px;
    text-align: center;
    transition: all 0.3s ease;
}

.feature-card:hover { 
    border-color: rgba(56,189,248,0.4);
    transform: translateY(-2px);
    box-shadow: 0 8px 30px rgba(6,11,19,0.5);
}

.feature-icon { font-size: 2rem; margin-bottom: 12px; }

.feature-title {
    font-family: 'Outfit', sans-serif;
    font-size: 1.15rem;
    font-weight: 600;
    color: #cbd5e1;
    margin-bottom: 6px;
}

.feature-desc { font-size: 0.85rem; color: #64748b; }

.section-title {
    font-family: 'Outfit', sans-serif;
    font-size: 1.3rem;
    font-weight: 600;
    color: #38bdf8;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(56,189,248,0.15);
}

.tab-nav button {
    color: #94a3b8 !important;
    font-weight: 500 !important;
}

.tab-nav button.selected {
    color: #38bdf8 !important;
    border-bottom: 2px solid #38bdf8 !important;
}
"""

HERO_HTML = f"""
<div class="hero-section">
    <div class="hero-title">👑 Crown & Crest</div>
    <p class="hero-subtitle">Soothing Winter Spa & Wellness Resorts — Olivia AI Receptionist</p>
    <span class="status-badge">
        <span class="status-dot"></span>
        Olivia is in the Winter Lounge & ready
    </span>
    <br/>
    <a class="call-button" href="https://agents-playground.livekit.io/" target="_blank">
        📞 Start Voice Call with Olivia
    </a>
    <p style="margin-top:16px; color:#475569; font-size:0.8rem;">
        Click above → Enter agent name: <code style="background:rgba(56,189,248,0.2);padding:2px 8px;border-radius:4px;color:#cbd5e1">crown-crest-receptionist</code> → Start session
    </p>
</div>

<div class="features-grid">
    <div class="feature-card">
        <div class="feature-icon">💆‍♀️</div>
        <div class="feature-title">Thermal Spa & Massages</div>
        <div class="feature-desc">Explore outdoor thermal lagoons, saunas, and custom massage sessions</div>
    </div>
    <div class="feature-card">
        <div class="feature-icon">🔥</div>
        <div class="feature-title">Winter Cozy Lounges</div>
        <div class="feature-desc">Cozy fireplaces, single-malt bars, and complimentary hot cocoa bars</div>
    </div>
    <div class="feature-card">
        <div class="feature-icon">🛏️</div>
        <div class="feature-title">Wellness Rooms</div>
        <div class="feature-desc">Book Cozy Twin, Thermal Double, or Crest Sanctuary Suites</div>
    </div>
    <div class="feature-card">
        <div class="feature-icon">❄️</div>
        <div class="feature-title">Soothing Locations</div>
        <div class="feature-desc">Soothing winter escapes in London, Manchester, and Edinburgh</div>
    </div>
    <div class="feature-card">
        <div class="feature-icon">🔊</div>
        <div class="feature-title">Natural Voice Agent</div>
        <div class="feature-desc">Speak naturally with Olivia, powered by Cartesia TTS & Groq Whisper STT</div>
    </div>
    <div class="feature-card">
        <div class="feature-icon">💳</div>
        <div class="feature-title">Secure Portal</div>
        <div class="feature-desc">Locked bookings with 24-hour winter invoice payment portal</div>
    </div>
</div>
"""

INSTRUCTIONS_MD = """
## How to talk to Olivia

1. **Click** the purple **"Start Voice Call with Olivia"** button above
2. The LiveKit Playground will open — click **"Open Console configuration"**
3. Under **Agent name**, type: `crown-crest-receptionist`
4. Click **"Save and start session"**
5. Allow microphone access when prompted — Olivia will greet you!

## What Olivia can do

| Capability | Example |
|---|---|
| Check availability | *"Do you have hot spring availability for next week?"* |
| Make a booking | *"Book a thermal double in Edinburgh for 4 nights"* |
| Modify booking | *"Can I change my spa check-in to Saturday?"* |
| Cancel reservation | *"I need to cancel booking HTL-..."* |
| Spa FAQ | *"What unique massage amenities does Manchester have?"* |
| Invoice by email | *"Send the invoice to my email"* |

## Branches & Wellness Specialties
- 🏙️ **London** — Crown Sanctuary Spa, glass-domed rooftop thermal baths & Michelin organic dining.  
- 🌧️ **Manchester** — Private sound-bath relaxation rooms, Finnish sauna suites & aromatherapy massage.  
- 🏴󠁧󠁢󠁳󠁣󠁴󠁿 **Edinburgh** — Geothermal outdoor hot springs lagoon, traditional Hammam scrubs & single-malt tasting.
"""

def get_status() -> str:
    """Return current system status."""
    now = datetime.datetime.now().strftime("%H:%M:%S")
    livekit_ok = bool(os.environ.get("LIVEKIT_URL"))
    google_ok = bool(os.environ.get("GOOGLE_API_KEY"))
    cartesia_ok = bool(os.environ.get("CARTESIA_API_KEY"))
    
    lines = [
        f"**Status check at {now}**\n",
        f"{'✅' if livekit_ok else '❌'} LiveKit voice infrastructure",
        f"{'✅' if google_ok else '❌'} Gemini LLM (Google AI)",
        f"{'✅' if cartesia_ok else '❌'} Cartesia TTS",
        f"✅ MCP Hotel Services (booking, availability, FAQ)",
        f"{'✅' if HAS_ZEROGPU else '⚡'} ZeroGPU Whisper {'(active)' if HAS_ZEROGPU else '(CPU fallback)'}",
    ]
    return "\n".join(lines)


def transcribe_demo(audio):
    """Gradio-compatible wrapper for ZeroGPU transcription."""
    if audio is None:
        return "Please record or upload audio first."
    try:
        text = transcribe_audio_gpu(audio)
        return f"**Transcribed:** {text}"
    except Exception as e:
        return f"Transcription error: {e}"


def check_payment_url(request: gr.Request):
    pay_ref = request.query_params.get("pay")
    if pay_ref:
        return [gr.update(visible=False), gr.update(visible=True), pay_ref]
    return [gr.update(visible=True), gr.update(visible=False), ""]

def load_payment_details(ref: str):
    from src.database import get_booking
    if not ref:
        return "No reference", "N/A", "0", ""
    booking = get_booking(ref)
    if not booking:
        return "Invalid booking", "N/A", "0", "Booking not found."
    
    status = booking["status"]
    if status == "BOOKED":
        return f"Ref: {booking['reference']}", "N/A", "0", "This booking is already confirmed and paid."
    if status in ("EXPIRED", "CANCELLED"):
        return f"Ref: {booking['reference']}", "N/A", "0", "This booking lock has expired or been cancelled."

    details = (
        f"**Guest:** {booking['guest_name']}\n\n"
        f"**Hotel:** Crown & Crest {booking['branch'].title()}\n\n"
        f"**Room:** {booking['room_type'].replace('_', ' ').title()}\n\n"
        f"**Check-in:** {booking['arrival_date']}\n\n"
        f"**Check-out:** {booking['checkout_date']}"
    )
    return f"Ref: {booking['reference']}", details, f"£{booking['total_cost']}", ""

def process_mock_payment(ref: str, card: str):
    from src.database import get_booking, record_payment, update_booking_status
    booking = get_booking(ref)
    if not booking or booking["status"] != "LOCKED":
        return "Payment failed: Booking is not in a payable state.", gr.update(interactive=False)
    
    mock_last4 = card[-4:] if len(card) >= 4 else "0000"
    record_payment(ref, booking["total_cost"], "FULL", mock_last4)
    new_reference = update_booking_status(ref, "BOOKED")

    def sync_send():
        try:
            import asyncio
            from src.mcp_server import _generate_invoice_html
            asyncio.run(_generate_invoice_html(new_reference, booking["guest_email"]))
        except Exception as e:
            print(f"Failed to send invoice: {e}", flush=True)
            
    import threading
    threading.Thread(target=sync_send, daemon=True).start()

    return f"✅ **Payment Successful!** Your confirmed reference is **{new_reference}**. An invoice has been emailed to {booking['guest_email']}.", gr.update(interactive=False)


with gr.Blocks(css=CSS, title="Crown & Crest — Olivia AI Receptionist") as demo:
    
    with gr.Column(visible=True) as main_ui:
        gr.HTML(HERO_HTML)

        with gr.Tabs(elem_classes=["tab-nav"]):
            with gr.Tab("📖 How to Connect"):
                gr.Markdown(INSTRUCTIONS_MD)

            with gr.Tab("📊 System Status"):
                gr.Markdown("### Live System Status")
                status_output = gr.Markdown(get_status())
                gr.Button("🔄 Refresh Status", variant="secondary").click(
                    fn=get_status,
                    outputs=status_output
                )

            with gr.Tab("⚡ ZeroGPU Transcription"):
                gr.Markdown("""
    ### Local Whisper Transcription (ZeroGPU A10G)
    Record or upload audio and get it transcribed locally using OpenAI Whisper running on an A10G GPU.
    This runs entirely on HuggingFace's hardware — no API calls, no rate limits.
    """)
                with gr.Row():
                    audio_input = gr.Audio(
                        sources=["microphone", "upload"],
                        type="filepath",
                        label="🎤 Record or Upload Audio"
                    )
                    transcription_output = gr.Markdown(
                        label="Transcription",
                        value="*Transcription will appear here...*"
                    )
                gr.Button("🚀 Transcribe with ZeroGPU", variant="primary").click(
                    fn=transcribe_demo,
                    inputs=audio_input,
                    outputs=transcription_output
                )

            with gr.Tab("ℹ️ About"):
                gr.Markdown("""
    ### Crown & Crest AI Receptionist

    **Olivia** is a production-grade AI voice receptionist built with:

    | Component | Technology |
    |---|---|
    | Voice Agent | LiveKit Agents SDK 1.6+ |
    | LLM | Google Gemini Flash Lite (via LangGraph ReAct) |
    | STT | Groq Whisper large-v3 |
    | TTS | Cartesia Sonic 3.5 |
    | Tool Calling | FastMCP + langchain-mcp-adapters |
    | GPU Transcription | OpenAI Whisper on ZeroGPU A10G |
    | Database | SQLite (bookings, locks) |
    | Payments | Native Gradio Portal |

    **Source:** [GitHub](https://github.com/Akhil-0412/Olivia-Hotel-Receptionist)
    """)

    with gr.Column(visible=False) as payment_ui:
        gr.Markdown("## 👑 Crown & Crest — Secure Checkout")
        pay_booking_id = gr.Textbox(visible=False)
        
        with gr.Row():
            with gr.Column():
                gr.Markdown("### Booking Summary")
                ref_disp = gr.Markdown("Loading...")
                details_disp = gr.Markdown("Loading...")
                total_disp = gr.Markdown("### Total Due: £0")
                msg_disp = gr.Markdown(elem_classes=["security-note"])
            
            with gr.Column():
                gr.Markdown("### Payment Details (Demo)")
                card_input = gr.Textbox(label="Card Number", placeholder="4242 4242 4242 4242", interactive=True)
                gr.Row([
                    gr.Textbox(label="Expiry (MM/YY)", placeholder="12/25", interactive=True),
                    gr.Textbox(label="CVC", placeholder="123", interactive=True)
                ])
                name_input = gr.Textbox(label="Cardholder Name", interactive=True)
                pay_btn = gr.Button("Secure Pay 🔒", variant="primary")
                pay_result = gr.Markdown()

        pay_booking_id.change(
            fn=load_payment_details,
            inputs=[pay_booking_id],
            outputs=[ref_disp, details_disp, total_disp, msg_disp]
        )
        
        pay_btn.click(
            fn=process_mock_payment,
            inputs=[pay_booking_id, card_input],
            outputs=[pay_result, pay_btn]
        )

    demo.load(
        fn=check_payment_url,
        inputs=[],
        outputs=[main_ui, payment_ui, pay_booking_id]
    )


    # -----------------------------------------------------------------------
    # HIDDEN API ENDPOINTS FOR NEXT.JS FRONTEND
    # -----------------------------------------------------------------------
    with gr.Group(visible=False):
        api_ref_in = gr.Textbox()
        api_name_in = gr.Textbox()
        
        api_guest_name = gr.Textbox()
        api_guest_email = gr.Textbox()
        api_guest_phone = gr.Textbox()
        api_arrival_date = gr.Textbox()
        api_checkout_date = gr.Textbox()
        api_room_type = gr.Textbox()
        api_branch = gr.Textbox()
        
        api_out = gr.JSON()
        
        def api_get_booking_fn(ref, name):
            from src.database import get_booking, get_payment_history
            b = get_booking(ref)
            if not b:
                return {"error": "Booking not found or name mismatch"}
            if b["guest_name"].lower() != name.lower().strip():
                return {"error": "Booking not found or name mismatch"}
            
            payments = get_payment_history(ref)
            amount_paid = sum(p["amount_gbp"] for p in payments if p["status"] == "COMPLETED")
            
            b_dict = dict(b)
            b_dict["amount_paid"] = amount_paid
            return b_dict
            
        def api_create_booking_fn(name, email, phone, arrival, checkout, room, branch):
            from src.database import create_booking, INVENTORY_CAPACITY
            import datetime
            try:
                arr_dt = datetime.date.fromisoformat(arrival)
                chk_dt = datetime.date.fromisoformat(checkout)
                nights = (chk_dt - arr_dt).days
                if nights <= 0:
                    return {"error": "Checkout date must be after arrival date."}
                
                branch_key = branch.lower()
                if branch_key not in INVENTORY_CAPACITY or room not in INVENTORY_CAPACITY[branch_key]:
                    return {"error": "Invalid branch or room type."}
                    
                price_per_night = INVENTORY_CAPACITY[branch_key][room]["price_gbp"]
                total_cost = price_per_night * nights
                
                ref = create_booking(
                    guest_name=name,
                    guest_email=email,
                    branch=branch_key,
                    room_type=room,
                    arrival_date=arrival,
                    nights=nights,
                    price_per_night=price_per_night,
                    total_cost=total_cost
                )
                return {"reference": ref}
            except Exception as e:
                import traceback
                traceback.print_exc()
                return {"error": str(e)}
                
        api_get_btn = gr.Button()
        api_get_btn.click(api_get_booking_fn, inputs=[api_ref_in, api_name_in], outputs=[api_out], api_name="api_get_booking")
        
        api_create_btn = gr.Button()
        api_create_btn.click(api_create_booking_fn, 
            inputs=[api_guest_name, api_guest_email, api_guest_phone, api_arrival_date, api_checkout_date, api_room_type, api_branch],
            outputs=[api_out], api_name="api_create_booking"
        )

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False
    )
