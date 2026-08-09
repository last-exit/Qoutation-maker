#!/bin/bash
# Stops the Odoo containers. Your data is in Docker volumes, not in the containers, so
# stopping and starting again loses nothing.
cd "$(dirname "$0")/odoo" || exit 1

echo "Stopping Odoo and PostgreSQL..."
docker compose stop

echo ""
echo "Stopped. Your data is safe — it lives in Docker volumes, not in the containers."
echo "Start again with:  ./run-odoo.command"
echo ""
echo "The Docker VM is still running in the background. To shut that down too and free"
echo "its memory, run:  colima stop"
read -r -p "Press Enter to close..."
