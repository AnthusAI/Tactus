"""
Create a simple sentiment classifier model for testing.

This creates a minimal PyTorch model that can classify text as positive/negative/neutral.
For demonstration purposes, this is a very simple model - in production you'd use
a proper transformer or fine-tuned model.
"""

import torch
import torch.nn as nn


class SimpleSentimentClassifier(nn.Module):
    """
    Ultra-simple sentiment classifier for testing.

    In reality, you'd use embeddings and proper NLP techniques,
    but for testing the model primitive, this is sufficient.
    """

    def __init__(self, vocab_size=1000, embed_dim=50, num_classes=3):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim)
        self.fc1 = nn.Linear(embed_dim, 64)
        self.fc2 = nn.Linear(64, num_classes)
        self.relu = nn.ReLU()

    def forward(self, x):
        # x should be a tensor of word indices
        # For simplicity, we'll just take the mean of embeddings
        if len(x.shape) == 0:
            # Single value - treat as one word
            x = x.unsqueeze(0).unsqueeze(0)
        elif len(x.shape) == 1:
            # List of values - treat as sequence
            x = x.unsqueeze(0)

        embedded = self.embedding(x)
        pooled = embedded.mean(dim=1)  # Simple mean pooling
        hidden = self.relu(self.fc1(pooled))
        output = self.fc2(hidden)
        return output


def create_model():
    """Create and save a simple sentiment model."""
    model = SimpleSentimentClassifier()

    # Set to eval mode
    model.eval()

    # Save the model
    torch.save(model, "sentiment_classifier.pt")
    print("✓ Created sentiment_classifier.pt")
    print("  - Input: Tensor of word indices")
    print("  - Output: [negative_score, neutral_score, positive_score]")
    print("  - Labels: ['negative', 'neutral', 'positive']")


if __name__ == "__main__":
    create_model()
