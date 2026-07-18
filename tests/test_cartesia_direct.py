import os
from cartesia import Cartesia
from dotenv import load_dotenv

load_dotenv()

def test():
    try:
        client = Cartesia(api_key=os.environ.get("Cartesia_API_KEY"))
        data = client.tts.generate(
            model_id="sonic-3.5",
            transcript="Hello, testing the Cartesia SDK directly.",
            voice={"mode": "id", "id": "c46cf1f6-49a1-4d67-9a57-ff859a4046d3"},
            output_format={
                "container": "raw",
                "encoding": "pcm_f32le",
                "sample_rate": 24000,
            },
        )
        for chunk in data:
            print(f"SUCCESS! Received audio chunk of size {len(chunk)}")
            break
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    test()
