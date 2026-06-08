#!/bin/sh
# Generate Mosquitto password file from environment or defaults
PASSWD_FILE="/mosquitto/config/passwd"

# Only generate if the file doesn't contain valid hashes (starts with $)
if ! grep -q '^\$' "$PASSWD_FILE" 2>/dev/null; then
  echo "Generating Mosquitto password file..."
  rm -f "$PASSWD_FILE"
  touch "$PASSWD_FILE"
  mosquitto_passwd -b "$PASSWD_FILE" platform-service platform123
  mosquitto_passwd -b "$PASSWD_FILE" org-demo demo123
  echo "Password file generated with users: platform-service, org-demo"
fi

exec mosquitto -c /mosquitto/config/mosquitto.conf
