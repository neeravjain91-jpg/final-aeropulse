import sys, base64
from pathlib import Path
target = Path(sys.argv[1])
b64_data = sys.argv[2]
target.parent.mkdir(parents=True, exist_ok=True)
target.write_bytes(base64.b64decode(b64_data.encode('utf-8')))
print(f'Successfully wrote {target} ({target.stat().st_size} bytes)')
