#!/bin/sh
# Local n8n only: bound to 127.0.0.1, telemetry and update checks off, data kept in the gitignored .n8n/ folder.
# No cloud account, no paid features. n8n 2.x ships with the Execute Command node disabled; it is switched on
# here (NODES_EXCLUDE empty) so the workflow can call the Python scripts in this repo.
cd "$(dirname "$0")" || exit 1
export N8N_USER_FOLDER="$PWD/.n8n"
export N8N_HOST=127.0.0.1
export N8N_LISTEN_ADDRESS=127.0.0.1
export N8N_PORT=5678
export N8N_DIAGNOSTICS_ENABLED=false
export N8N_VERSION_NOTIFICATIONS_ENABLED=false
export N8N_TEMPLATES_ENABLED=false
export N8N_PERSONALIZATION_ENABLED=false
export NODES_EXCLUDE='[]'
export N8N_RESTRICT_FILE_ACCESS_TO="$PWD/data"
# UB credentials: load UBL_USER and UBL_PASS from the owner-only file into this process's environment so
# the login script (reader/login_flow.py env_credentials) can read them. Lines are parsed, never sourced
# or evaluated, and nothing is echoed. The values never touch the repo, workflow JSON or logs.
UBL_ENV_FILE="${UBL_ENV_FILE:-$HOME/.config/ubl.env}"
if [ -r "$UBL_ENV_FILE" ] && [ "$(stat -f '%Lp' "$UBL_ENV_FILE")" = "600" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      UBL_USER=*) v=${line#UBL_USER=}; k=UBL_USER ;;
      UBL_PASS=*) v=${line#UBL_PASS=}; k=UBL_PASS ;;
      *) continue ;;
    esac
    case "$v" in \"*\") v=${v#\"}; v=${v%\"} ;; \'*\') v=${v#\'}; v=${v%\'} ;; esac
    export "$k=$v"
  done < "$UBL_ENV_FILE"
  unset line v k
else
  echo "run-n8n: $UBL_ENV_FILE missing or not mode 600; UB login credentials not loaded" >&2
fi
# n8n 2.44.4 needs Node >= 24; use the nvm copy if present.
[ -s "$HOME/.nvm/nvm.sh" ] && . "$HOME/.nvm/nvm.sh" && nvm use 24 >/dev/null
exec npx --yes n8n@2.44.4 start
