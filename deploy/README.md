# EC2 deployment of django-demos

This manually triggered workflow deploys the selected main-branch commit of
django-demos into the existing Python 3.7 / Django 3.2 virtualenv. Merge the
invoicer UI PR first. This does not deploy django-wiest.world or django-users,
resolve dependencies, upgrade Python/Django, or run database migrations.
Local settings, secrets, uploaded files and HAProxy configuration stay in place.
The workflow must be on main before it appears under Actions.

## One-time EC2 setup

Confirm the paths below against your actual server. Install `curl`, `tar` and
`flock` if absent. The deployment account is ec2-user. Keep SSH reachable from
the runner using your approved network access route; a private-only host needs
a suitable runner/network route before this workflow can connect.

1. Install `deploy/django.service` as `/etc/systemd/system/django.service`.
   This deliberately preserves your current development server for compatibility;
   replacing it with a production application server is separate work.
2. Stop the existing nohup/runserver process, including any autoreloader child,
   by its verified PID. Do not use a broad `pkill python`. Ensure port 8000 is
   free, then run `sudo systemctl daemon-reload` and
   `sudo systemctl enable --now django.service`. Confirm the site works through HAProxy.
3. Grant ec2-user passwordless access via a file validated with `visudo`:

   ```sudoers
   ec2-user ALL=(root) NOPASSWD: /usr/bin/systemctl start django.service, /usr/bin/systemctl stop django.service, /usr/bin/systemctl is-active --quiet django.service
   ```

   Verify your systemctl path is `/usr/bin/systemctl`; adjust the script and rule
   together if necessary.
4. Create `~/.config/django-deploy.conf` with mode 600:

   ```bash
   PROJECT_DIR=/home/ec2-user/django-wiest.world
   VENV_DIR=/home/ec2-user/app_3.7
   HEALTH_URL=http://127.0.0.1:8000/django/login/
   HEALTH_HOST=wiest.world
   ```

   Verify these paths and that the health URL returns HTTP 200. The health check
   verifies the local HTTP endpoint; validate authenticated invoicer CRUD and
   HAProxy/TLS manually after the first deployment.

## GitHub setup and operation

Create environment `ec2-production` in django-demos, restricted to main, with:

| Environment secret | Value |
| --- | --- |
| `EC2_HOST` | Reachable hostname or IP, without username |
| `EC2_SSH_KEY` | Dedicated private SSH key authorized for ec2-user |
| `EC2_KNOWN_HOSTS` | Verified SSH known_hosts entry for that host |

Verify the SSH host key independently on EC2. Do not blindly trust a key
retrieved over the same network connection. Apply any desired environment
review requirement. No AWS credentials are required for this SSH workflow.

After merging the workflow and UI PRs, choose Actions → Deploy demos to EC2 →
Run workflow → main. Merging alone does not deploy. The workflow builds a pure
Python wheel on a modern runner, then installs only that package on EC2 using
`--no-deps` to preserve the working legacy environment and avoid the existing
Selenium dependency mismatch. Build checks confirm invoicer templates are included.

Deployment briefly stops Django, takes a consistent SQLite backup, installs
the wheel, checks Django and pending migrations, restarts, and checks HTTP.
Backups and uploaded wheels remain on EC2; monitor disk usage and prune only
after confirming a working release. Backups contain sensitive application data.
Static files currently continue to use the existing DEBUG/runserver arrangement;
this workflow intentionally does not run collectstatic without STATIC_ROOT.

## Failure and rollback

A failed install/check attempts to start the service again but does not
automatically restore code. The workflow reports failure; inspect Actions and
`journalctl -u django.service`. For code rollback, stop django.service and restore
the saved virtualenv archive into the SAME virtualenv path, then start the
service and check HTTP. Remove the failed virtualenv contents before extracting
to avoid leaving new files behind. Do not restore SQLite for a code-only rollback;
that would discard newer application data. Database restoration requires a
separate deliberate decision. Do not rerun migrations automatically to repair
a failed deployment. Updates requiring migrations or new dependencies need an
expanded deployment procedure.
