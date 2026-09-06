import base64
from pathlib import Path

def write_b64(path, b64_str):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(base64.b64decode(b64_str.encode('utf-8')))
    print(f'Wrote {p} ({p.stat().st_size} bytes)')
