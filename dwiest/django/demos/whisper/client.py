"""SigV4 transport adapted from Bookmarks; Whisper has independent configuration."""
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings


class ServiceError(Exception):
    def __init__(self, message, status=503):
        self.status = status
        super().__init__(message)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class WhisperClient:
    def __init__(self, user):
        import os
        self.base = str(getattr(settings, 'WHISPER_SERVICE_URL', os.environ.get('WHISPER_SERVICE_URL', ''))).rstrip('/')
        self.region = str(getattr(settings, 'WHISPER_SERVICE_REGION', os.environ.get('WHISPER_SERVICE_REGION', 'us-east-1')))
        try:
            parsed = urlsplit(self.base)
            valid = (parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password
                     and not parsed.query and not parsed.fragment and parsed.path.endswith('/service')
                     and not any(c.isspace() for c in self.base))
        except ValueError:
            valid = False
        if not valid or not re.fullmatch(r'[a-z0-9-]+', self.region):
            raise ServiceError('Configure WHISPER_SERVICE_URL (HTTPS, ending /service) and WHISPER_SERVICE_REGION on the server.')
        self.user_reference = str(user.pk)

    def request(self, method, path, payload=None, key=None):
        if not (path == '/files' or path.startswith(('/files/', '/files?', '/jobs/', '/jobs?')) or path == '/jobs') or '://' in path or '#' in path or '\r' in path or '\n' in path:
            raise ServiceError('Invalid media service path.', 400)
        data = json.dumps(payload).encode('utf-8') if payload is not None else None
        headers = {'X-User-Reference': self.user_reference, 'Content-Type': 'application/json'}
        if key:
            headers['Idempotency-Key'] = key
        url = self.base + path
        try:
            credentials = boto3.Session().get_credentials()
            if credentials is None:
                raise ServiceError('The Django server needs AWS role credentials for media service access.')
            signed = AWSRequest(method=method, url=url, data=data, headers=headers)
            SigV4Auth(credentials.get_frozen_credentials(), 'execute-api', self.region).add_auth(signed)
            request = Request(url, data=data, headers=dict(signed.headers), method=method)
            with build_opener(NoRedirect()).open(request, timeout=25) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise ServiceError('The media service response exceeded its size limit.')
            result = json.loads(raw.decode('utf-8'))
            if not isinstance(result, dict):
                raise ValueError()
            return result
        except HTTPError as exc:
            message = 'Media service returned HTTP {}.'.format(exc.code)
            try:
                result = json.loads(exc.read(8192).decode('utf-8'))
                if isinstance(result.get('message'), str):
                    message = result['message'][:500]
            except (ValueError, UnicodeError, AttributeError):
                pass
            raise ServiceError(message, exc.code) from None
        except (URLError, TimeoutError, OSError, BotoCoreError, ClientError):
            raise ServiceError('The media service could not be reached. Retry the same operation.') from None
        except (ValueError, UnicodeError):
            raise ServiceError('The media service returned an invalid response.') from None
