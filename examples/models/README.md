# Model Files

This directory contains ML model files used by Tactus procedures.

For canonical Model primitive syntax and patterns, see:

- `docs/model-primitive.md`
- `llms.txt`

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
Model "my_classifier" {
  type = "pytorch",
  path = "examples/models/my_model.pt",
  device = "cpu",  -- or "cuda", "mps"
  labels = {"class1", "class2", "class3"},
  input = { data = "array" },
  output = { prediction = "string" }
}

Procedure {
  input = { data = field.list{required = true} },
  output = { prediction = field.string{required = true} },
  function(input)
    local classifier = Model("my_classifier")
    local result = classifier(input.data)
    local out = result.output or result
    return { prediction = out }
  end
}
```

## HTTP Models

No installation required - just point to any REST endpoint:

```lua
Model "api_classifier" {
  type = "http",
  endpoint = "https://your-api.com/classify",
  timeout = 30.0,
  headers = {
    Authorization = "Bearer YOUR_TOKEN"
  },
  input = { text = "string" },
  output = { label = "string", confidence = "float" }
}
```

## Model Types Supported

- `pytorch` - PyTorch .pt files (requires torch)
- `http` - REST API endpoints (no dependencies)
- More coming: sklearn, onnx, transformers, etc.
