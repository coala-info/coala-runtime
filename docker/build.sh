#!/bin/bash
# Build script for Coala Runtime Docker images

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Building Coala Runtime Docker images...${NC}\n"

# Build Python image
echo -e "${GREEN}Building Python executor image...${NC}"
docker build \
    -f "$SCRIPT_DIR/Dockerfile.python" \
    -t coala-runtime-python:latest \
    "$PROJECT_ROOT"

echo -e "${GREEN}✓ Python image built successfully${NC}\n"

# Build R image
echo -e "${GREEN}Building R executor image...${NC}"
docker build \
    -f "$SCRIPT_DIR/Dockerfile.r" \
    -t coala-runtime-r:latest \
    "$PROJECT_ROOT"

echo -e "${GREEN}✓ R image built successfully${NC}\n"

echo -e "${BLUE}All images built successfully!${NC}"
echo -e "Images available:"
echo -e "  - coala-runtime-python:latest"
echo -e "  - coala-runtime-r:latest"
