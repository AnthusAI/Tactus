"""
PyTorch model backend for .pt file inference.
"""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PyTorchModelBackend:
    """Model backend that loads and runs PyTorch models."""

    def __init__(self, path: str, device: str = "cpu", labels: list[str] | None = None):
        """
        Initialize PyTorch model backend.

        Args:
            path: Path to .pt model file
            device: Device to run on ('cpu', 'cuda', 'mps')
            labels: Optional list of class labels for classification
        """
        self.path = Path(path)
        self.device = device
        self.labels = labels
        self.model = None

    def _load_model(self):
        """Lazy load the model on first use."""
        if self.model is not None:
            return

        try:
            import torch
        except ImportError:
            raise ImportError("PyTorch not installed. Install with: pip install torch")

        if not self.path.exists():
            raise FileNotFoundError(f"Model file not found: {self.path}")

        self.model = torch.load(self.path, map_location=self.device)
        self.model.eval()
        logger.info(f"Loaded PyTorch model from {self.path}")

    async def predict(self, input_data: Any) -> Any:
        """
        Run PyTorch model inference.

        Args:
            input_data: Input tensor or data convertible to tensor

        Returns:
            Model output (tensor or label if labels provided)
        """
        return self.predict_sync(input_data)

    def predict_sync(self, input_data: Any) -> Any:
        """
        Synchronous PyTorch inference.

        Args:
            input_data: Input tensor or data convertible to tensor

        Returns:
            Model output (tensor or label if labels provided)
        """
        self._load_model()

        try:
            import torch
        except ImportError:
            raise ImportError("PyTorch not installed. Install with: pip install torch")

        # Convert input to tensor if needed
        if not isinstance(input_data, torch.Tensor):
            if isinstance(input_data, (list, tuple)):
                input_tensor = torch.tensor(input_data)
            else:
                input_tensor = torch.tensor([input_data])
        else:
            input_tensor = input_data

        # Move to device
        input_tensor = input_tensor.to(self.device)

        # Run inference
        with torch.no_grad():
            output = self.model(input_tensor)

        # If labels provided, return class label
        if self.labels:
            if output.dim() > 1:
                # Classification - get argmax
                predicted_idx = output.argmax(dim=-1).item()
            else:
                # Single value - round to nearest index
                predicted_idx = int(round(output.item()))

            if 0 <= predicted_idx < len(self.labels):
                return self.labels[predicted_idx]
            else:
                logger.warning(f"Predicted index {predicted_idx} out of range for labels")
                return predicted_idx

        # Return raw output
        if output.numel() == 1:
            return output.item()
        else:
            return output.cpu().numpy().tolist()
