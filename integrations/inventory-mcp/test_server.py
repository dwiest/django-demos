import asyncio
import importlib.util
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from io import BytesIO

spec = importlib.util.spec_from_file_location('inventory_lambda', Path(__file__).with_name('lambda_function.py'))
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class InventoryMCPTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            'DJANGO_API_BASE_URL': 'https://example.test/inventory/api/',
            'DJANGO_API_AUTHORIZATION': 'Basic test-secret',
            'MCP_AUTH_TOKEN': 'client-secret', 'PUBLIC_HOST': 'example.test',
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.mcp = server.make_server({})

    def call(self, name, args):
        return asyncio.run(self.mcp.call_tool(name, args))

    def event(self, body):
        return {'version': '2.0', 'routeKey': 'ANY /api/inventory-mcp',
                'rawPath': '/api/inventory-mcp', 'rawQueryString': '',
                'headers': {'host': 'example.test', 'authorization': 'Bearer client-secret',
                            'content-type': 'application/json',
                            'accept': 'application/json, text/event-stream'},
                'requestContext': {'domainName': 'example.test', 'stage': '$default',
                                   'http': {'method': 'POST', 'path': '/api/inventory-mcp',
                                            'sourceIp': '127.0.0.1', 'protocol': 'HTTP/1.1'}},
                'body': json.dumps(body), 'isBase64Encoded': False}

    def test_tool_catalog(self):
        tools = asyncio.run(self.mcp.list_tools())
        self.assertEqual(len(tools), 13)
        by_name = {t.name: t for t in tools}
        adjust = by_name['adjust_inventory_quantity']
        self.assertIn('idempotency_key', adjust.inputSchema['required'])
        self.assertTrue(adjust.annotations.idempotentHint)
        self.assertFalse(by_name['create_inventory_entry'].annotations.idempotentHint)

    def test_entry_filters_and_history_routes(self):
        with patch.object(server, 'django_request', return_value={'results': []}) as request:
            self.call('search_inventory_entries', {'item_id': 2, 'list_id': 3, 'term': 'apple'})
            self.assertEqual(request.call_args.args, ('GET', 'entries/'))
            self.assertEqual(request.call_args.kwargs['query'],
                             {'item': 2, 'inventory_list': 3, 'term': 'apple', 'page': 1, 'page_size': 40})
            self.call('list_inventory_transactions', {'entry_id': 9})
            self.assertEqual(request.call_args.args, ('GET', 'entries/9/transactions/'))

    def test_adjustment_preserves_retry_payload(self):
        args = {'entry_id': 9, 'operation': 'add', 'quantity': 3,
                'idempotency_key': 'capture-1-entry-9', 'metadata': {'confidence': .9}}
        with patch.object(server, 'django_request', return_value={'after': 6}) as request:
            self.call('adjust_inventory_quantity', args)
            first = request.call_args
            self.call('adjust_inventory_quantity', args)
            self.assertEqual(first, request.call_args)
            self.assertEqual(first.kwargs['payload']['source'], 'mcp')
            self.assertEqual(first.kwargs['payload']['idempotency_key'], args['idempotency_key'])

    def test_invalid_quantities_never_reach_api(self):
        with patch.object(server, 'django_request') as request:
            for quantity in [-1, True, 1.5, 2147483648]:
                with self.assertRaises(Exception):
                    self.call('adjust_inventory_quantity', dict(entry_id=1, operation='add',
                              quantity=quantity, idempotency_key='test'))
            request.assert_not_called()

    def test_patch_only_supplied_fields(self):
        with patch.object(server, 'django_request', return_value={'name': 'New'}) as request:
            self.call('update_inventory_item', {'item_id': 1, 'changes': {'name': 'New'}})
            self.assertEqual(request.call_args.kwargs['payload'], {'name': 'New'})
            with self.assertRaises(Exception):
                self.call('update_inventory_item', {'item_id': 1, 'changes': {'quantity': 3}})

    def test_api_credentials_and_redirect_error(self):
        opener = unittest.mock.MagicMock()
        response = opener.open.return_value.__enter__.return_value
        response.status = 200
        response.read.return_value = b'{"results": []}'
        with patch.object(server, 'build_opener', return_value=opener):
            self.assertEqual(server.django_request('GET', 'items/'), {'results': []})
            req = opener.open.call_args.args[0]
            self.assertEqual(req.get_header('Authorization'), 'Basic test-secret')
            opener.open.side_effect = HTTPError(req.full_url, 302, 'Found', {}, BytesIO(b''))
            with self.assertRaises(server.DjangoAPIError) as error:
                server.django_request('GET', 'items/')
            self.assertEqual(error.exception.status, 302)
        self.assertIsNone(server.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.test'))

    def test_lambda_initialize_and_tools_list(self):
        for method, params in [('initialize', {'protocolVersion': '2025-03-26',
                'capabilities': {}, 'clientInfo': {'name': 'test', 'version': '1'}}),
                ('tools/list', {})]:
            result = server.lambda_handler(self.event({'jsonrpc': '2.0', 'id': 1,
                                                       'method': method, 'params': params}), None)
            self.assertEqual(result['statusCode'], 200, result)
            self.assertIn('result', json.loads(result['body']))

    def test_lambda_tool_call(self):
        event = self.event({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
                           'params': {'name': 'get_inventory_entry', 'arguments': {'entry_id': 9}}})
        with patch.object(server, 'django_request', return_value={'id': 9, 'quantity': 4}) as request:
            result = server.lambda_handler(event, None)
            self.assertEqual(result['statusCode'], 200, result)
            self.assertFalse(json.loads(result['body'])['result'].get('isError', False))
            request.assert_called_once_with('GET', 'entries/9/', query=None, payload=None)

    def test_creation_payloads(self):
        with patch.object(server, 'django_request', return_value={'id': 1}) as request:
            self.call('create_inventory_item', {'name': 'Apples', 'description': 'Fruit'})
            self.assertEqual(request.call_args.kwargs['payload'],
                             {'name': 'Apples', 'description': 'Fruit', 'status': 0})
            self.call('create_inventory_entry', {'item_id': 1, 'list_id': 2, 'quantity': 0})
            self.assertEqual(request.call_args.kwargs['payload'],
                             {'item': 1, 'inventory_list': 2, 'quantity': 0, 'status': 0})

    def test_api_errors_become_tool_errors(self):
        with patch.object(server, 'django_request', side_effect=server.DjangoAPIError(403, 'forbidden')):
            result = server.lambda_handler(self.event({'jsonrpc': '2.0', 'id': 3,
                'method': 'tools/call', 'params': {'name': 'get_inventory_entry',
                                                 'arguments': {'entry_id': 9}}}), None)
            payload = json.loads(result['body'])['result']
            self.assertTrue(payload['isError'])
            self.assertIn('403:forbidden', payload['content'][0]['text'])

    def test_lambda_auth_and_body_limit(self):
        event = self.event({})
        event['headers']['authorization'] = 'Bearer wrong'
        self.assertEqual(server.lambda_handler(event, None)['statusCode'], 401)
        os.environ.pop('MCP_AUTH_TOKEN')
        self.assertEqual(server.lambda_handler(event, None)['statusCode'], 503)
        os.environ['MCP_AUTH_TOKEN'] = 'client-secret'
        event['headers']['authorization'] = 'Bearer client-secret'
        event['body'] = 'x' * (server.MAX_BODY_SIZE + 1)
        self.assertEqual(server.lambda_handler(event, None)['statusCode'], 413)


if __name__ == '__main__':
    unittest.main()
