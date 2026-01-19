#!/usr/bin/env python3
"""Test channel loading."""

import sys
sys.path.insert(0, "/Users/ryan.porter/Projects/Tactus_4")

print(f"sys.stdin.isatty() = {sys.stdin.isatty()}")
print()

from tactus.adapters.channels import load_default_channels

channels = load_default_channels()
print(f"Loaded {len(channels)} channel(s):")
for ch in channels:
    print(f"  - {ch.channel_id}")
