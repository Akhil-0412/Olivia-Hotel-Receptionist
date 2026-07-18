import sys
import os
print("PATH inside -m module:")
for p in sys.path:
    print(" -", p)
try:
    import livekit
    print("LIVEKIT:", getattr(livekit, '__file__', 'NAMESPACE'))
except Exception as e:
    print("LIVEKIT ERROR:", e)
try:
    import src
    print("SRC:", getattr(src, '__file__', 'NAMESPACE'))
except Exception as e:
    print("SRC ERROR:", e)
