import sys
import types
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Ensure torch mock exists if torch is not installed so scipy / sklearn / tcn never fail
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

from app.main import app
