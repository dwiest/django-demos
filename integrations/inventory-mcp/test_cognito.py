import base64
import importlib.util
import json
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch, Mock

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
import cognito_auth as auth

spec = importlib.util.spec_from_file_location('oauth_lambda', Path(__file__).with_name('lambda_function.py'))
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class CognitoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self):
        self.env = patch.dict(os.environ, {
            'AUTH_MODE': 'cognito', 'COGNITO_USER_POOL_ID': 'us-east-1_TestPool',
            'COGNITO_CLIENT_ID': 'inventory-client', 'COGNITO_ALLOWED_SUBJECTS': 'owner-sub',
            'PUBLIC_MCP_URL': 'https://example.test/api/inventory-mcp',
            'COGNITO_DOMAIN': 'https://test.auth.us-east-1.amazoncognito.com',
            'MCP_AUTH_TOKEN': 'old-static-token',
        })
        self.env.start(); self.addCleanup(self.env.stop)
        self.client = patch.object(auth, 'key_client', return_value=Mock())
        client = self.client.start(); self.addCleanup(self.client.stop)
        client.return_value.get_signing_key_from_jwt.return_value.key = self.key.public_key()

    def token(self, **changes):
        now = int(time.time())
        claims = dict(iss=auth.configuration()[0], aud=os.environ['PUBLIC_MCP_URL'],
                      client_id='inventory-client', token_use='access', sub='owner-sub',
                      exp=now+300, iat=now, scope='openid inventory/read inventory/write')
        claims.update(changes)
        return jwt.encode(claims, self.key, algorithm='RS256', headers={'kid': 'test-key'})

    def event(self, path='/api/inventory-mcp', method='POST', token=''):
        return dict(rawPath=path, headers={'authorization': 'Bearer '+token},
                    requestContext={'http': {'method': method}}, body='{}')

    def test_valid_access_token(self):
        self.assertEqual(auth.verify('Bearer '+self.token())['sub'], 'owner-sub')

    def test_reject_invalid_claims(self):
        for changes in [dict(iss='https://evil.test'), dict(aud='https://other.test'),
                        dict(client_id='voicemail-client'), dict(token_use='id'),
                        dict(exp=int(time.time())-60), dict(iat=int(time.time())+300)]:
            with self.subTest(changes=changes), self.assertRaises(auth.AuthError) as error:
                auth.verify('Bearer '+self.token(**changes))
            self.assertEqual(error.exception.status, 401)

    def test_reject_other_users_and_missing_scopes(self):
        for changes in [dict(sub='another-user'), dict(scope='inventory/read')]:
            with self.assertRaises(auth.AuthError) as error:
                auth.verify('Bearer '+self.token(**changes))
            self.assertEqual(error.exception.status, 403)

    def test_reject_signature_tampering(self):
        token = self.token()
        parts=token.split('.')
        parts[1]=base64.urlsafe_b64encode(json.dumps({'sub':'owner-sub'}).encode()).decode().rstrip('=')
        with self.assertRaises(auth.AuthError):
            auth.verify('Bearer '+'.'.join(parts))

    def test_missing_audience_rejected(self):
        claims=jwt.decode(self.token(), options={'verify_signature': False})
        claims.pop('aud')
        with self.assertRaises(auth.AuthError):
            auth.verify('Bearer '+jwt.encode(claims,self.key,algorithm='RS256'))

    def test_public_discovery_and_challenge(self):
        for path in ['/.well-known/oauth-protected-resource/api/inventory-mcp',
                     '/.well-known/oauth-protected-resource', '/.well-known/oauth-authorization-server']:
            result=server.lambda_handler(self.event(path, 'GET'), None)
            self.assertEqual(result['statusCode'],200)
        metadata=auth.authorization_metadata()
        self.assertEqual(metadata['code_challenge_methods_supported'],['S256'])
        self.assertEqual(metadata['issuer'],auth.discovery()['authorization_servers'][0])
        result=server.lambda_handler(self.event(),None)
        self.assertEqual(result['statusCode'],401)
        self.assertIn('resource_metadata=',result['headers']['WWW-Authenticate'])

    def test_no_static_token_fallback_and_configuration_fail_closed(self):
        self.assertEqual(server.lambda_handler(self.event(token='old-static-token'),None)['statusCode'],401)
        os.environ.pop('COGNITO_ALLOWED_SUBJECTS')
        self.assertEqual(server.lambda_handler(self.event(),None)['statusCode'],503)


if __name__ == '__main__':
    unittest.main()
