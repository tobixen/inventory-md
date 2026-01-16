#!/bin/bash
# Release script: creates a tag, pushes to GitHub, and updates AUR
# Usage: ./scripts/release.sh <version>
# Example: ./scripts/release.sh 0.3.3

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
AUR_DIR="${REPO_DIR}/../inventory-md.aur"

if [ -z "$1" ]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 0.3.3"
    exit 1
fi

VERSION="$1"
TAG="v${VERSION}"

cd "$REPO_DIR"

# Check we're on main branch
BRANCH=$(git branch --show-current)
if [ "$BRANCH" != "main" ] && [ "$BRANCH" != "master" ]; then
    echo "Warning: You're on branch '$BRANCH', not main/master"
    read -p "Continue anyway? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check for uncommitted changes
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Error: You have uncommitted changes. Please commit or stash them first."
    exit 1
fi

# Check if tag already exists
if git rev-parse "$TAG" >/dev/null 2>&1; then
    echo "Error: Tag $TAG already exists"
    exit 1
fi

# Create and push the tag
echo "Creating tag $TAG..."
git tag -sa "$TAG" -m "Release $VERSION"

echo "Pushing to origin..."
git push origin "$BRANCH"
git push origin "$TAG"

# Update AUR
if [ -x "$AUR_DIR/update-aur.sh" ]; then
    echo "Updating AUR package..."
    "$AUR_DIR/update-aur.sh" "$VERSION"
else
    echo "Warning: AUR update script not found at $AUR_DIR/update-aur.sh"
fi

echo ""
echo "Release $VERSION complete!"
