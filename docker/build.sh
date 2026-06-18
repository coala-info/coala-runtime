#!/bin/bash
# Build Coala Runtime Docker images (linux/amd64 and linux/arm64 / Apple Silicon).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Single platform for local builds (auto-detect host unless overridden).
detect_platform() {
    case "$(uname -m)" in
        arm64 | aarch64) echo "linux/arm64" ;;
        x86_64 | amd64) echo "linux/amd64" ;;
        *) echo "linux/amd64" ;;
    esac
}

# COALA_DOCKER_PLATFORM=linux/arm64  — force one platform (local load)
# COALA_DOCKER_PLATFORMS=linux/amd64,linux/arm64  — multi-arch (requires buildx + push)
PLATFORM="${COALA_DOCKER_PLATFORM:-$(detect_platform)}"
PLATFORMS="${COALA_DOCKER_PLATFORMS:-$PLATFORM}"
PUSH="${COALA_DOCKER_PUSH:-0}"
BUILDX_BUILDER="${COALA_DOCKER_BUILDX_BUILDER:-coala-runtime-builder}"
PYTHON_IMAGE="${COALA_DOCKER_PYTHON_IMAGE:-coala-runtime-python:latest}"
R_IMAGE="${COALA_DOCKER_R_IMAGE:-coala-runtime-r:latest}"

ensure_buildx() {
    if ! docker buildx version >/dev/null 2>&1; then
        echo "docker buildx is required for multi-platform builds." >&2
        exit 1
    fi
    if ! docker buildx inspect "$BUILDX_BUILDER" >/dev/null 2>&1; then
        docker buildx create --name "$BUILDX_BUILDER" --driver docker-container --use
    else
        docker buildx use "$BUILDX_BUILDER"
    fi
    docker buildx inspect --bootstrap >/dev/null
}

build_image() {
    local dockerfile=$1
    local tag=$2
    shift 2
    local -a extra_args=("$@")

    if [[ "$PLATFORMS" == *","* ]]; then
        ensure_buildx
        local -a bx=(buildx build --platform "$PLATFORMS" -f "$dockerfile" -t "$tag")
        bx+=("${extra_args[@]}")
        if [[ "$PUSH" == "1" ]]; then
            bx+=(--push)
        else
            echo -e "${YELLOW}Multi-platform build without COALA_DOCKER_PUSH=1; use --push to publish.${NC}" >&2
            bx+=(--load)
        fi
        bx+=("$PROJECT_ROOT")
        docker "${bx[@]}"
        return
    fi

    docker build --platform "$PLATFORMS" -f "$dockerfile" -t "$tag" "${extra_args[@]}" "$PROJECT_ROOT"
}

echo -e "${BLUE}Building Coala Runtime Docker images...${NC}"
echo -e "Platform(s): ${PLATFORMS}"
if [[ "$PUSH" == "1" ]]; then
    echo -e "Publish: push to registry"
fi
echo

echo -e "${GREEN}Building Python executor image...${NC}"
build_image "$SCRIPT_DIR/Dockerfile.python" "$PYTHON_IMAGE"
echo -e "${GREEN}✓ Python image built${NC}\n"

echo -e "${GREEN}Building R executor image...${NC}"
build_image "$SCRIPT_DIR/Dockerfile.r" "$R_IMAGE"
echo -e "${GREEN}✓ R image built${NC}\n"

echo -e "${BLUE}All images built successfully!${NC}"
echo -e "Images available:"
echo -e "  - $PYTHON_IMAGE"
echo -e "  - $R_IMAGE"
if [[ "$PLATFORMS" == *","* && "$PUSH" != "1" ]]; then
    echo -e "${YELLOW}Note: --load with multiple platforms only loads one arch; set COALA_DOCKER_PUSH=1 to publish a multi-arch manifest.${NC}"
fi
