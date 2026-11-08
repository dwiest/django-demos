# EC2 deployment of django-demos

This manually triggered workflow deploys the selected main-branch commit of
django-demos into the existing Python 3.7 / Django 3.2 virtualenv. Merge the
invoicer UI PR first. This does not deploy django-wiest.world or django-users,
resolve dependencies, upgrade Python/Django, or run database migrations.
Local settings, secrets, uploaded files and HAProxy configuration stay in place.
The workflow must be on main before it appears under Actions.

## One-time EC2 setup

Confirm the paths below against your actual server. Install `curl`, `tar` and
`flock`, `sha256sum`, `runuser` and AWS CLI if absent. The deployment account is
ec2-user. SSM Agent must be online. The instance must reach S3 as well as SSM
through outbound connectivity or VPC endpoints. No inbound SSH is needed.
The AWS CLI must be available to the root SSM shell and use the instance role.

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

The workflow targets instance `i-0169208b66edd709c` in `us-east-1` and uploads
releases under `s3://dwiest-artifacts/django-demos/`. It sends AWS-RunShellScript
to that instance and waits for its individual command invocation, checking both
status and exit code. SSM downloads as root, verifies SHA-256 digests, then runs
the existing installer as ec2-user. Application deployment code is trusted code:
SendCommand through this document grants root command execution on this instance.

### AWS IAM setup

The existing `wiest-world-github-production` and `wiest-world-github-staging`
roles may belong to the marketing website. Leave them unchanged. In IAM →
Identity providers, check for `token.actions.githubusercontent.com`.

Deploy `deploy/github-oidc-role.json` as a CloudFormation template in the
instance's AWS account. Choose **Template is ready → Upload a template file**
and upload that JSON file. A selected default template does not configure OIDC.
Leave `CreateGitHubProvider=false` when the provider already exists; set it true
only if absent. Acknowledge IAM resource creation. The stack creates a dedicated
role and outputs `DeployRoleArn`, without changing the website roles.

The trust policy matches `repo:dwiest/django-demos:environment:ec2-production`
and audience `sts.amazonaws.com`. If this repository has opted into immutable
OIDC subjects, update the subject to its actual format before deployment.
Create GitHub environment `ec2-production`, **restrict deployment branches to
main**, and add environment **variable** `AWS_DEPLOY_ROLE_ARN` from the stack's
`DeployRoleArn` output. The role ARN is not a secret. No access keys or SSH
secrets are used. The role can write only this S3 prefix, send shell commands
only to this instance using AWS-RunShellScript, and read invocation results.

Attach `deploy/instance-artifacts-policy.json` to the instance's existing IAM
role, retaining its SSM permissions. This allows reads only from the release
prefix. Confirm AWS CLI credentials resolve to the instance role in the root
SSM shell. Bucket policies, endpoint policies and organization policies must
also permit these operations. Artifacts use SSE-S3; an enforced customer KMS
key policy requires corresponding workflow and IAM changes. Keep the bucket
private. No ListBucket or access to other prefixes is needed.

After merging the workflow and UI PRs, choose Actions → Deploy demos to EC2 →
Run workflow → main. Merging alone does not deploy. The workflow builds a pure
Python wheel on a modern runner, then installs only that package on EC2 using
`--no-deps` to preserve the working legacy environment and avoid the existing
Selenium dependency mismatch. Build checks confirm invoicer templates are included.

Deployment briefly stops Django, takes a consistent SQLite backup, installs
the wheel, checks Django and pending migrations, restarts, and checks HTTP.
Backups and downloaded wheels remain on EC2, and releases remain in S3; monitor disk usage and prune only
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
