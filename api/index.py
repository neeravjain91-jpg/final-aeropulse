import sys
import types
import urllib.parse
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
    Vercel rewrites /api/(.*) to /api/index.py?__route__=$1.
    This adapter extracts the original requested route from __route__ query parameter,
    restores scope['path'] and cleans scope['query_string'] so FastAPI routes seamlessly.
    """
    def __init__(self, fastapi_app):
        self.app = fastapi_app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            qs = scope.get("query_string", b"").decode("utf-8")
            if "__route__" in qs:
                params = urllib.parse.parse_qs(qs, keep_blank_values=True)
                route_val = params.pop("__route__", [None])[0]
                if route_val:
                    route_val = "/" + route_val.lstrip("/")
                    target_path = route_val if route_val.startswith("/api/") else "/api" + route_val
                    scope["path"] = target_path
                    scope["raw_path"] = target_path.encode("utf-8")
                    scope["query_string"] = urllib.parse.urlencode(params, doseq=True).encode("utf-8")
            elif scope.get("path") in ("/api/index.py", "/api/index", "/api", "/api/"):
                headers = dict(scope.get("headers", []))
                matched = headers.get(b"x-matched-path", b"").decode("utf-8") or headers.get(b"x-forwarded-uri", b"").decode("utf-8")
                if matched and matched not in ("/api/index.py", "/api/index", "/api", "/api/"):
                    clean_path = matched.split("?")[0]
                    target_path = clean_path if clean_path.startswith("/api/") else "/api" + clean_path
                    scope["path"] = target_path
                    scope["raw_path"] = target_path.encode("utf-8")

        await self.app(scope, receive, send)

app = VercelASGIAdapter(_base_app)
