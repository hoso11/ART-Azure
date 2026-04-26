#!/usr/bin/env bash
# Build the two custom ART images for Azure deployment.
#
# Usage:
#   ./scripts/azure/build.sh
#   TAG=v1 ./scripts/azure/build.sh
#   TAG=v2 DOCKERHUB_USERNAME=hoso30 ./scripts/azure/build.sh
set -euo pipefail

TAG="${TAG:-latest}"
USERNAME="${DOCKERHUB_USERNAME:-hoso30}"
NEXT_PUBLIC_APP_NAME="${NEXT_PUBLIC_APP_NAME:-ART Manufacturing}"
NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-/api/v1}"
NEXT_PUBLIC_MINIO_URL="${NEXT_PUBLIC_MINIO_URL:-}"
INTERNAL_API_URL="${INTERNAL_API_URL:-http://localhost:8000}"

cd "$(dirname "$0")/../.."

BACKEND="${USERNAME}/art-backend:${TAG}"
FRONTEND="${USERNAME}/art-frontend:${TAG}"

echo ""
echo "== Build ${BACKEND} =="
docker build -f backend/Dockerfile.azure -t "${BACKEND}" ./backend

echo ""
echo "== Build ${FRONTEND} =="
docker build -f frontend/Dockerfile.azure \
  --build-arg NEXT_PUBLIC_APP_NAME="${NEXT_PUBLIC_APP_NAME}" \
  --build-arg NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL}" \
  --build-arg NEXT_PUBLIC_MINIO_URL="${NEXT_PUBLIC_MINIO_URL}" \
  --build-arg INTERNAL_API_URL="${INTERNAL_API_URL}" \
  -t "${FRONTEND}" ./frontend

echo ""
echo "Built:"
echo "  ${BACKEND}"
echo "  ${FRONTEND}"
