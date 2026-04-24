#!/bin/bash
# Build script for Ordex library distribution
# Creates sdist for PyPI upload

set -e

VERSION="1.1.0"
echo "Building Ordex v${VERSION}..."

# Clean previous builds
rm -rf dist/
mkdir -p dist/

# Build source distribution
echo "Creating sdist..."
python3 setup.py sdist

echo "Build complete!"
ls -la dist/

echo ""
echo "To upload to PyPI:"
echo "  twine check dist/*"
echo "  twine upload dist/*"
echo ""
echo "Or with token:"
echo "  twine upload dist/* -u __token__ -p \$PYPI_TOKEN"