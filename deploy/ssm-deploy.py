"""Upload a release and wait for this instance's SSM invocation result."""
import hashlib
import os
import pathlib
import re
import shlex
import time

import boto3
from botocore.exceptions import ClientError


def request(release, wheel, hashes, commit, bucket, instance):
    directory = "/home/ec2-user/" + release
    commands = ["set -eu", "umask 077", "mkdir " + shlex.quote(directory)]
    for name in (wheel, "install-demos.sh"):
        commands.append("aws s3 cp " + shlex.quote("s3://" + bucket + "/django-demos/" + release + "/" + name)
                        + " " + shlex.quote(directory + "/" + name) + " --region us-east-1")
        commands.append("printf '%s\\n' " + shlex.quote(hashes[name] + "  " + directory + "/" + name)
                        + " | sha256sum -c -")
    commands += ["chown -R ec2-user:ec2-user " + shlex.quote(directory),
                 "runuser -u ec2-user -- env HOME=/home/ec2-user bash "
                 + shlex.quote(directory + "/install-demos.sh") + " " + shlex.quote(directory)
                 + " " + shlex.quote(commit)]
    return dict(InstanceIds=[instance], DocumentName="AWS-RunShellScript", TimeoutSeconds=120,
                Parameters={"commands": ["\n".join(commands)], "executionTimeout": ["900"]},
                Comment="Deploy django-demos " + commit)


def main():
    commit = os.environ["GITHUB_SHA"]
    assert re.fullmatch(r"[0-9a-f]{40}", commit)
    run = os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"]
    assert re.fullmatch(r"[0-9]+-[0-9]+", run)
    release = "django-deploy-" + commit + "-" + run
    wheels = list(pathlib.Path("dist").glob("*.whl"))
    assert len(wheels) == 1
    files = [wheels[0], pathlib.Path("deploy/install-demos.sh")]
    bucket, instance = os.environ["ARTIFACT_BUCKET"], os.environ["INSTANCE_ID"]
    s3 = boto3.client("s3", region_name="us-east-1")
    ssm = boto3.client("ssm", region_name="us-east-1")
    hashes = {}
    for path in files:
        data = path.read_bytes()
        hashes[path.name] = hashlib.sha256(data).hexdigest()
        s3.put_object(Bucket=bucket, Key="django-demos/" + release + "/" + path.name, Body=data,
                      ServerSideEncryption="AES256")
    command = ssm.send_command(**request(release, wheels[0].name, hashes, commit, bucket, instance))
    command_id = command["Command"]["CommandId"]
    print("SSM command:", command_id, flush=True)
    deadline = time.monotonic() + 1100
    while time.monotonic() < deadline:
        try:
            result = ssm.get_command_invocation(CommandId=command_id, InstanceId=instance)
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "InvocationDoesNotExist":
                raise
        else:
            if result["Status"] not in ("Pending", "InProgress", "Delayed", "Cancelling"):
                print(result.get("StandardOutputContent", ""))
                print(result.get("StandardErrorContent", ""))
                if result["Status"] != "Success" or result["ResponseCode"] != 0:
                    raise SystemExit("Deployment failed: " + result["Status"])
                print("Deployed", commit)
                return
        time.sleep(5)
    raise SystemExit("Timed out waiting; inspect SSM command " + command_id
                     + " before retrying. The remote command may still be running.")


if __name__ == "__main__":
    main()
