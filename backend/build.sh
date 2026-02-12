#!/bin/bash
set -euo pipefail

echo "Installing backend dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "Running database migrations..."
python ../manage.py migrate --noinput

echo "Collecting static assets..."
python ../manage.py collectstatic --noinput --clear
