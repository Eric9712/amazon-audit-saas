#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "---------------------------------------"
echo "🚀 STARTING BUILD PROCESS"
echo "---------------------------------------"

echo "📦 Upgrading pip..."
pip install --upgrade pip

echo "📦 Installing requirements..."
pip install -r requirements.txt

echo "🎨 Collecting static files..."
python manage.py collectstatic --no-input

echo "💾 Applying database migrations..."
python manage.py migrate

echo "👤 Creating Superuser (if needed)..."
python create_superuser.py

echo "---------------------------------------"
echo "✅ BUILD FINISHED SUCCESSFULLY"
echo "---------------------------------------"
