import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app_gradio import api_create_booking_fn

print(api_create_booking_fn(
    'Akhil', 'akhileshwarsanathana0104@gmail.com', '+44 000000000',
    '2026-11-04', '2026-11-10', 'standard_twin', 'manchester'
))
