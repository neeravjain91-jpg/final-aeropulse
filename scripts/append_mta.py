import sys, base64
from pathlib import Path

target = Path('docs/AEROPULSE_X_MASTER_TECHNICAL_AUDIT.md')
target.parent.mkdir(exist_ok=True)
data = base64.b64decode(sys.argv[1].encode('utf-8')).decode('utf-8')

with open(target, 'a', encoding='utf-8') as f:
    f.write(data + '\n\n')

print(f'Appended to {target} (Total: {target.stat().st_size} bytes)')
