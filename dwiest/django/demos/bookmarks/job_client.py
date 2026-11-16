"""SigV4 job-service client; endpoints are controlled by server configuration only."""
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen, HTTPRedirectHandler, build_opener

import boto3
from botocore.auth import SigV4Auth
from botocore.exceptions import BotoCoreError, ClientError
from botocore.awsrequest import AWSRequest

from .ai_credentials import AIError, configured
from django.views.decorators.debug import sensitive_variables


class JobError(AIError):
    def __init__(self, message, status=None, details=None):
        super().__init__(message, details)
        self.status = status
        self.transient = status is None or status in (408, 429) or status >= 500


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def connection():
    url = str(configured('BOOKMARKS_JOB_SERVICE_URL', '')).strip().rstrip('/')
    region = str(configured('BOOKMARKS_JOB_SERVICE_REGION', configured('AWS_REGION', 'us-east-1')))
    try:
        parsed = urlsplit(url)
        valid = (parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password
                 and not parsed.query and not parsed.fragment and parsed.path.endswith('/service')
                 and not any(c.isspace() for c in url))
    except ValueError:
        valid = False
    if not valid or not re.fullmatch(r'[a-z0-9-]+', region):
        raise AIError('Configure BOOKMARKS_JOB_SERVICE_URL (HTTPS, ending /service) and BOOKMARKS_JOB_SERVICE_REGION on the server.')
    return url, region


class JobClient:
    def __init__(self, owner, expected_url=None):
        self.base, self.region = connection()
        if expected_url and expected_url != self.base:
            raise AIError('This attempt belongs to a different job-service endpoint. Restore its server configuration before continuing.')
        self.user_reference = str(owner.pk)

    @sensitive_variables()
    def request(self, method, path, payload=None, key=None):
        if not path.startswith('/') or '://' in path or '#' in path:
            raise AIError('Invalid job-service path.')
        data = json.dumps(payload).encode('utf-8') if payload is not None else None
        headers = {'X-User-Reference': self.user_reference, 'Content-Type': 'application/json'}
        if key:
            headers['Idempotency-Key'] = key
        url = self.base + path
        try:
            credentials = boto3.Session().get_credentials()
            if credentials is None:
                raise AIError('The Django server needs AWS role credentials for job-service access.')
            signed = AWSRequest(method=method, url=url, data=data, headers=headers)
            SigV4Auth(credentials.get_frozen_credentials(), 'execute-api', self.region).add_auth(signed)
            req = Request(url, data=data, headers=dict(signed.headers), method=method)
            # Never forward signed credentials to redirect destinations.
            with build_opener(NoRedirect()).open(req, timeout=12) as response:
                body = response.read(2 * 1024 * 1024 + 1)
            if len(body) > 2 * 1024 * 1024:
                raise AIError('The job-service response exceeded its size limit.')
            result = json.loads(body.decode('utf-8'))
            if not isinstance(result, dict):
                raise ValueError()
            return result
        except HTTPError as exc:
            message = 'Job service returned HTTP {}.'.format(exc.code)
            try:
                parsed = json.loads(exc.read(8192).decode('utf-8'))
                if isinstance(parsed.get('message'), str):
                    message += ' ' + parsed['message'][:500]
            except (ValueError, UnicodeError, AttributeError):
                pass
            raise JobError(message, exc.code, {'http_status': exc.code}) from None
        except (URLError, TimeoutError, OSError, BotoCoreError, ClientError):
            raise JobError('The job service could not be reached. The same operation will be retried safely.') from None
        except (ValueError, UnicodeError):
            raise AIError('The job service returned an invalid JSON response.') from None

    def submit(self, payload, key):
        return self.request('POST', '/jobs', payload, key)

    def job(self, job_id, result=False):
        if not re.fullmatch(r'[a-f0-9]{32}', job_id):
            raise AIError('Invalid saved job reference.')
        return self.request('GET', '/jobs/' + job_id + ('/result' if result else ''))
