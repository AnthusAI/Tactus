#!/bin/bash

# Script to generate Electron app icons from a source PNG
# Usage: ./scripts/generate-icons.sh [path-to-source-icon.png]
# If no path is provided, defaults to ../Tactus-web/assets/icon.png

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Source icon (default or from argument)
SOURCE_ICON="${1:-../../Tactus-web/assets/icon.png}"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
RESOURCES_DIR="$PROJECT_DIR/resources"

echo -e "${BLUE}=== Electron Icon Generator ===${NC}"
echo ""

# Check if source icon exists
if [ ! -f "$SOURCE_ICON" ]; then
    echo -e "${RED}Error: Source icon not found at: $SOURCE_ICON${NC}"
    echo "Usage: ./scripts/generate-icons.sh [path-to-source-icon.png]"
    exit 1
fi

echo -e "${GREEN}✓${NC} Source icon: $SOURCE_ICON"

# Get source icon dimensions
DIMENSIONS=$(sips -g pixelWidth -g pixelHeight "$SOURCE_ICON" 2>/dev/null | grep -E "pixelWidth|pixelHeight" | awk '{print $2}' | paste -sd 'x' -)
echo -e "${GREEN}✓${NC} Source dimensions: $DIMENSIONS"
echo ""

# Create resources directory if it doesn't exist
mkdir -p "$RESOURCES_DIR"
echo -e "${BLUE}Step 1: Creating Linux PNG icon (512x512)${NC}"
sips -z 512 512 "$SOURCE_ICON" --out "$RESOURCES_DIR/app-icon.png" > /dev/null 2>&1
echo -e "${GREEN}✓${NC} Created: $RESOURCES_DIR/app-icon.png"
echo ""

# Generate macOS ICNS
echo -e "${BLUE}Step 2: Generating macOS ICNS icon${NC}"
TEMP_ICONSET="$PROJECT_DIR/icon.iconset"
mkdir -p "$TEMP_ICONSET"

echo "  Generating icon sizes..."
sips -z 16 16     "$SOURCE_ICON" --out "$TEMP_ICONSET/icon_16x16.png" > /dev/null 2>&1
sips -z 32 32     "$SOURCE_ICON" --out "$TEMP_ICONSET/icon_16x16@2x.png" > /dev/null 2>&1
sips -z 32 32     "$SOURCE_ICON" --out "$TEMP_ICONSET/icon_32x32.png" > /dev/null 2>&1
sips -z 64 64     "$SOURCE_ICON" --out "$TEMP_ICONSET/icon_32x32@2x.png" > /dev/null 2>&1
sips -z 128 128   "$SOURCE_ICON" --out "$TEMP_ICONSET/icon_128x128.png" > /dev/null 2>&1
sips -z 256 256   "$SOURCE_ICON" --out "$TEMP_ICONSET/icon_128x128@2x.png" > /dev/null 2>&1
sips -z 256 256   "$SOURCE_ICON" --out "$TEMP_ICONSET/icon_256x256.png" > /dev/null 2>&1
sips -z 512 512   "$SOURCE_ICON" --out "$TEMP_ICONSET/icon_256x256@2x.png" > /dev/null 2>&1
sips -z 512 512   "$SOURCE_ICON" --out "$TEMP_ICONSET/icon_512x512.png" > /dev/null 2>&1
sips -z 1024 1024 "$SOURCE_ICON" --out "$TEMP_ICONSET/icon_512x512@2x.png" > /dev/null 2>&1

echo "  Converting to ICNS..."
iconutil -c icns "$TEMP_ICONSET" -o "$RESOURCES_DIR/app-icon.icns"
rm -rf "$TEMP_ICONSET"
echo -e "${GREEN}✓${NC} Created: $RESOURCES_DIR/app-icon.icns"
echo ""

# Generate Windows ICO
echo -e "${BLUE}Step 3: Generating Windows ICO icon (256x256)${NC}"

# Check if ImageMagick is available
if command -v magick &> /dev/null; then
    magick "$SOURCE_ICON" -resize 256x256 "$RESOURCES_DIR/app-icon.ico"
    echo -e "${GREEN}✓${NC} Created: $RESOURCES_DIR/app-icon.ico"
elif command -v convert &> /dev/null; then
    convert "$SOURCE_ICON" -resize 256x256 "$RESOURCES_DIR/app-icon.ico"
    echo -e "${GREEN}✓${NC} Created: $RESOURCES_DIR/app-icon.ico"
else
    echo -e "${RED}⚠${NC}  Warning: ImageMagick not found. Skipping ICO generation."
    echo "    Install with: brew install imagemagick"
    echo "    Or electron-builder will try to convert PNG to ICO during build."
fi
echo ""

# Summary
echo -e "${GREEN}=== Icon Generation Complete ===${NC}"
echo ""
echo "Generated files:"
ls -lh "$RESOURCES_DIR"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "  1. Review icons in: $RESOURCES_DIR"
echo "  2. Run: npm run package:mac (or package:win, package:linux)"
echo "  3. Test the built application"
echo ""
