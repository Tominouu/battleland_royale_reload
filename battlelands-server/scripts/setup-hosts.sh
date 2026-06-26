#!/bin/bash
# Add /etc/hosts entry to redirect PlayFab API calls to local server
# Usage: sudo bash setup-hosts.sh [title-id]

TITLE_ID="${1:-FC88D}"
DOMAIN="${TITLE_ID}.playfabapi.com"

if grep -q "$DOMAIN" /etc/hosts 2>/dev/null; then
    echo "$DOMAIN already in /etc/hosts"
else
    echo "127.0.0.1 $DOMAIN" >> /etc/hosts
    echo "Added $DOMAIN -> 127.0.0.1 to /etc/hosts"
fi

# Also add common PlayFab domains
for d in "playfabapi.com" "*.playfabapi.com"; do
    if ! grep -q "$d" /etc/hosts 2>/dev/null; then
        echo "127.0.0.1 $d" >> /etc/hosts
    fi
done
echo "Done. Restart the game to use local server."
