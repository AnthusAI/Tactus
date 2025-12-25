# Model Files

This directory contains ML model files used by Tactus procedures.

## PyTorch Models

To use PyTorch models (`.pt` files), install PyTorch:

```bash
pip install torch
```

### Creating a Model

```python
import torch
import torch.nn as nn

class MyModel(nn.Module):
    def __init__(self):
        super().__init__()
        # Define your model architecture
        self.fc = nn.Linear(10, 3)

    def forward(self, x):
        return self.fc(x)

# Create and save
model = MyModel()
model.eval()
torch.save(model, "my_model.pt")
```

### Using in Tactus

```lua
model("my_classifier", {
    type = "pytorch",
    path = "examples/models/my_model.pt",
    device = "cpu",  -- or "cuda", "mps"
    labels = {"class1", "class2", "class3"}
})

procedure({
    input = {data = {type = "array"}},
    output = {prediction = {type = "string"}},
    state = {}
}, function()
    local result = My_classifier.predict(input.data)
    return {prediction = result}
end)
```

## HTTP Models

No installation required - just point to any REST endpoint:

```lua
model("api_classifier", {
    type = "http",
    endpoint = "https://your-api.com/classify",
    timeout = 30.0,
    headers = {
        Authorization = "Bearer YOUR_TOKEN"
    }
})
```

## Model Types Supported

- `pytorch` - PyTorch .pt files (requires torch)
- `http` - REST API endpoints (no dependencies)
- More coming: sklearn, onnx, transformers, etc.
