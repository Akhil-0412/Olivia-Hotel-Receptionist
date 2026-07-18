import os
import json
import urllib.request
from dotenv import load_dotenv

load_dotenv()

def test():
    req = urllib.request.Request(
        'https://api.cartesia.ai/models',
        headers={
            'X-API-Key': os.environ.get('Cartesia_API_KEY'),
            'Cartesia-Version': '2024-06-10'
        }
    )
    res = urllib.request.urlopen(req)
    models = json.loads(res.read())
    print([m['id'] for m in models])

if __name__ == "__main__":
    test()
