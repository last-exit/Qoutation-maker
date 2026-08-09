#!/bin/bash
# Double-clickable launcher for the Odoo app.
#
# Two things have to be up: the Docker VM (Colima), and the Odoo + Postgres containers.
# This starts whichever is not already running, waits until Odoo actually answers, and opens
# the browser. Safe to run when everything is already up — it just opens the browser.
cd "$(dirname "$0")/odoo" || exit 1

if ! command -v colima >/dev/null 2>&1; then
    echo "Colima is not installed. Run:  brew install colima docker docker-compose"
    read -r -p "Press Enter to exit..."
    exit 1
fi

# Colima is the Linux VM the containers run inside. Docker commands fail without it, with an
# error that does not mention Colima at all, so check it first.
if ! colima status >/dev/null 2>&1; then
    echo "Starting the Docker VM (this takes ~30s the first time each reboot)..."
    colima start --cpu 4 --memory 8 --disk 60 --vm-type vz --mount-type virtiofs || {
        echo "Could not start Colima."
        read -r -p "Press Enter to exit..."
        exit 1
    }
fi

echo "Starting Odoo and PostgreSQL..."
docker compose up -d || {
    echo "Could not start the containers. See the errors above."
    read -r -p "Press Enter to exit..."
    exit 1
}

# Odoo takes a few seconds to load its modules after the container reports "started", so wait
# for it to actually serve a page rather than opening the browser onto a connection error.
echo -n "Waiting for Odoo to come up"
for _ in $(seq 1 60); do
    if curl -fsS -o /dev/null http://127.0.0.1:8069/web/login 2>/dev/null; then
        echo " ready."
        open "http://127.0.0.1:8069"
        echo ""
        echo "Odoo is running at http://127.0.0.1:8069"
        echo "Log in as 'admin'. The password is ODOO_ADMIN_PASSWORD in odoo/.env"
        echo ""
        echo "To stop it later:  ./stop-odoo.command"
        exit 0
    fi
    echo -n "."
    sleep 2
done

echo ""
echo "Odoo did not respond within two minutes. Check the logs with:"
echo "    cd odoo && docker compose logs -f odoo"
read -r -p "Press Enter to exit..."
