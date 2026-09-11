import sys
import types
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Safe Torch Mock for Vercel Serverless runtime
if "torch" not in sys.modules:
    try:
        import torch
    except ImportError:
        mock_torch = types.ModuleType("torch")
        class Tensor: pass
        mock_torch.Tensor = Tensor
        mock_torch.float32 = object
        mock_torch.no_grad = lambda: lambda fn: fn
        mock_torch.load = lambda *args, **kwargs: None
        mock_nn = types.ModuleType("torch.nn")
        mock_nn.Module = object
        mock_nn.Conv1d = object
        mock_nn.BatchNorm1d = object
        mock_nn.ReLU = object
        mock_nn.ELU = object
        mock_nn.Dropout = object
        mock_torch.nn = mock_nn
        mock_functional = types.ModuleType("torch.nn.functional")
        mock_torch.nn.functional = mock_functional
        sys.modules["torch"] = mock_torch
        sys.modules["torch.nn"] = mock_nn
        sys.modules["torch.nn.functional"] = mock_functional

from app.main import app as _base_app

class VercelASGIAdapter:
    """
    Vercel rewrites /api/(.*) to /api/index.py which can set scope['path'] to '/api/index.py'.
    This adapter extracts the original requested path from x-matched-path / x-forwarded-uri
    and ensures FastAPI routes correctly.
    """
    def __init__(self, fastapi_app):
        self.app = fastapi_app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            path = scope.get("path", "")
            headers = dict(scope.get("headers", []))
            
            # Check if path is the script file itself
            if path in ("/api/index.py", "/api/index", "/api", "/api/"):
                matched = (
                    headers.get(b"x-matched-path", b"").decode("utf-8")
                    or headers.get(b"x-forwarded-uri", b"").decode("utf-8")
                    or headers.get(b"x-real-path", b"").decode("utf-8")
                    or headers.get(b"x-vercel-matched-path", b"").decode("utf-8")
                )
                if matched and matched not in ("/api/index.py", "/api/index", "/api", "/api/"):
                    clean_path = matched.split("?")[0]
                    scope["path"] = clean_path
                    scope["raw_path"] = clean_path.encode("utf-8")

        await self.app(scope, receive, send)

app = VercelASGIAdapter(_base_app)
