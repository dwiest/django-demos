#!/usr/bin/env bash
# Runs as ec2-user; configuration stays on the EC2 instance.
set -euo pipefail
release=${1:?release directory required}
commit=${2:?commit required}
[[ $commit =~ ^[0-9a-f]{40}$ ]] || exit 2
source "$HOME/.config/django-deploy.conf"
: "${PROJECT_DIR:?}" "${VENV_DIR:?}" "${HEALTH_URL:?}" "${HEALTH_HOST:?}"
python="$VENV_DIR/bin/python"
exec 9>"$HOME/.django-deploy.lock"
flock -n 9 || { echo 'Another deployment is running'; exit 1; }
shopt -s nullglob
wheels=("$release"/*.whl)
[[ ${#wheels[@]} == 1 ]] || exit 2
cd "$PROJECT_DIR"
"$python" -c 'import sys, django; assert sys.version_info[:2] == (3, 7); assert django.VERSION[:2] == (3, 2)'
# Validate the replacement application only after installation so broken URLs
# in the installed release cannot block their own repair.
sudo -n /usr/bin/systemctl is-active --quiet django.service
backup="$HOME/django-deploy-backups/$(date -u +%Y%m%dT%H%M%SZ)-$commit"
mkdir -p "$backup"
chmod 700 "$backup"
# Preserve the whole environment for manual rollback, including package data.
tar -czf "$backup/virtualenv.tar.gz" -C "$VENV_DIR" .
sudo -n /usr/bin/systemctl stop django.service
restart() { sudo -n /usr/bin/systemctl start django.service; }
trap restart EXIT
# SQLite backup API also handles databases using WAL mode.
"$python" - "$backup/db.sqlite3" <<'PY'
import os, sqlite3, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wiest-world.settings')
# Reading DATABASES needs settings only, not application initialization.
from django.conf import settings
db = settings.DATABASES['default']
assert db['ENGINE'] == 'django.db.backends.sqlite3'
with sqlite3.connect('file:' + str(db['NAME']) + '?mode=ro', uri=True) as src:
    with sqlite3.connect(sys.argv[1]) as dst:
        src.backup(dst)
PY
"$python" -m pip install --no-index --no-deps --no-build-isolation --force-reinstall "${wheels[0]}"
"$python" manage.py check
# This first workflow is for schema-neutral package updates. Never create migrations here.
"$python" manage.py migrate --check
sudo -n /usr/bin/systemctl start django.service
trap - EXIT
curl --fail --silent --show-error --retry 10 --retry-connrefused --retry-delay 2 \
  --max-time 15 -H "Host: $HEALTH_HOST" "$HEALTH_URL" -o /dev/null
printf '%s\n' "$commit" > "$HOME/.django-demos-deployed-commit"
echo "Deployed $commit; rollback backup: $backup"
