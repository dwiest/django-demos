"""Private S3 objects and owner-partitioned DynamoDB metadata.

The SQL models remain available only for the one-time legacy import.
"""
import hashlib
import json
import os
import re
import time
from functools import wraps
from urllib.parse import quote

import boto3
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeSerializer
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings


class StorageError(Exception):
    def __init__(self, message, status=503):
        self.status = status
        super().__init__(message)


def aws_errors(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except (ClientError, BotoCoreError):
            raise StorageError('File storage could not complete the request. Please retry.') from None
    return wrapped


def setting(name, default=''):
    return getattr(settings, name, os.environ.get(name, default))


class FileStore:
    def __init__(self, owner_id):
        self.owner = 'USER#' + str(owner_id)
        self.bucket = setting('FILE_MANAGER_BUCKET')
        self.table_name = setting('FILE_MANAGER_TABLE')
        if not self.bucket or not self.table_name:
            raise StorageError('Configure FILE_MANAGER_BUCKET and FILE_MANAGER_TABLE on the server.')
        region = setting('FILE_MANAGER_REGION', 'us-east-1')
        self.table = boto3.resource('dynamodb', region_name=region).Table(self.table_name)
        self.ddb = boto3.client('dynamodb', region_name=region)
        self.s3 = boto3.client('s3', region_name=region, config=Config(signature_version='s3v4'))

    def key(self, file_id):
        if not re.fullmatch(r'[a-f0-9]{32}|[a-f0-9-]{36}', str(file_id)):
            raise StorageError('File not found.', 404)
        return {'pk': self.owner, 'sk': 'FILE#' + file_id}

    def transact(self, actions):
        serializer = TypeSerializer()
        packed = []
        for kind, values in actions:
            values = dict(values, TableName=self.table_name)
            for name in ('Key', 'Item', 'ExpressionAttributeValues'):
                if name in values:
                    values[name] = {k: serializer.serialize(v) for k, v in values[name].items()}
            packed.append({kind: values})
        self.ddb.transact_write_items(TransactItems=packed)

    @aws_errors
    def quota(self):
        saved = self.table.get_item(Key={'pk': 'CONFIG', 'sk': 'QUOTA'}, ConsistentRead=True).get('Item', {})
        return {name: int(saved.get(name, setting('FILE_MANAGER_' + name.upper(), default))) for name, default in (
            ('max_files', 100), ('max_filesize', 1073741824), ('max_total_filesize', 5368709120))}

    @aws_errors
    def summary(self):
        return self.table.get_item(Key={'pk': self.owner, 'sk': 'USAGE'}, ConsistentRead=True).get('Item', {'files': 0, 'size': 0})

    @aws_errors
    def get(self, file_id, include_deleted=False):
        item = self.table.get_item(Key=self.key(file_id), ConsistentRead=True).get('Item')
        if not item or (item['status'] == 'deleted' and not include_deleted):
            raise StorageError('File not found.', 404)
        return item

    @aws_errors
    def listing(self, cursor=None):
        params = dict(KeyConditionExpression=Key('pk').eq(self.owner) & Key('sk').begins_with('FILE#'),
                      ConsistentRead=True, Limit=100)
        if cursor:
            params['ExclusiveStartKey'] = dict(self.key(cursor))
        page = self.table.query(**params)
        return ([item for item in page['Items'] if item['status'] != 'deleted'],
                page.get('LastEvaluatedKey', {}).get('sk', '')[5:] or None)

    @aws_errors
    def register(self, payload, operation):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{16,128}', operation or ''):
            raise StorageError('Supply an upload operation key.', 400)
        name = payload.get('original_name')
        size = payload.get('size')
        if not isinstance(name, str) or not name.strip() or len(name) > 255 or any(ord(c) < 32 for c in name):
            raise StorageError('Supply a filename of at most 255 characters.', 400)
        if isinstance(size, bool) or not isinstance(size, int) or not 1 <= size <= 1073741824:
            raise StorageError('Choose a file between 1 byte and 1 GiB.', 400)
        content_type = payload.get('content_type') or 'application/octet-stream'
        if not isinstance(content_type, str) or len(content_type) > 255 or not re.fullmatch(r'[\w.+-]+/[\w.+-]+', content_type):
            content_type = 'application/octet-stream'
        fingerprint = hashlib.sha256(json.dumps([name, size, content_type]).encode()).hexdigest()
        file_id = hashlib.sha256((self.owner + ':' + operation).encode()).hexdigest()[:32]
        item_key = self.key(file_id)
        existing = self.table.get_item(Key=item_key, ConsistentRead=True).get('Item')
        if existing:
            if existing.get('fingerprint') != fingerprint:
                raise StorageError('This upload key was already used for another file.', 409)
            return self.registration(existing)
        quota = self.quota()
        if quota['max_filesize'] > 0 and size > quota['max_filesize']:
            raise StorageError('This file exceeds the maximum file size.', 400)
        now = int(time.time())
        item = dict(item_key, file_id=file_id, name=name, original_name=name, size=size,
                    content_type=content_type, description='', created_at=now, status='uploading',
                    upload_until=now + 3600, fingerprint=fingerprint,
                    object_key='files/{}/{}'.format(self.owner[5:], file_id))
        try:
            self.reserve(item, quota)
        except ClientError as exc:
            if exc.response['Error']['Code'] != 'TransactionCanceledException':
                raise
            # A response lost after a successful registration is safe to retry.
            existing = self.table.get_item(Key=item_key, ConsistentRead=True).get('Item')
            if existing and existing.get('fingerprint') == fingerprint:
                return self.registration(existing)
            raise StorageError('Upload quota reached or another upload is being saved. Retry after freeing space.', 409)
        return self.registration(item)

    def reserve(self, item, quota, enforce=True):
        values = {':one': 1, ':size': int(item['size'])}
        conditions = []
        if enforce and quota['max_files'] > 0:
            values[':max_files'] = quota['max_files'] - 1
            conditions.append('(attribute_not_exists(files) OR files <= :max_files)')
        if enforce and quota['max_total_filesize'] > 0:
            remaining = quota['max_total_filesize'] - int(item['size'])
            if remaining < 0:
                raise StorageError('This file exceeds your total storage quota.', 409)
            values[':remaining'] = remaining
            conditions.append('(attribute_not_exists(#size) OR #size <= :remaining)')
        usage = dict(Key={'pk': self.owner, 'sk': 'USAGE'}, UpdateExpression='ADD files :one, #size :size',
                     ExpressionAttributeNames={'#size': 'size'}, ExpressionAttributeValues=values)
        if conditions:
            usage['ConditionExpression'] = ' AND '.join(conditions)
        self.transact([('Put', {'Item': item, 'ConditionExpression': 'attribute_not_exists(pk)'}), ('Update', usage)])

    def registration(self, item):
        if item['status'] == 'ready':
            return {'file': item}
        if item['status'] != 'uploading' or item['upload_until'] <= int(time.time()):
            raise StorageError('This upload has expired. Start a new upload.', 410)
        # Always store an inert content type. Downloads explicitly set a safe response type.
        fields = {'Content-Type': 'application/octet-stream', 'x-amz-meta-file-id': item['file_id']}
        upload = self.s3.generate_presigned_post(
            Bucket=self.bucket, Key=item['object_key'], Fields=fields,
            Conditions=[{'Content-Type': fields['Content-Type']}, {'x-amz-meta-file-id': item['file_id']},
                        ['content-length-range', int(item['size']), int(item['size'])]],
            ExpiresIn=min(900, int(item['upload_until']) - int(time.time())))
        return {'file': item, 'upload': upload}

    @aws_errors
    def complete(self, file_id):
        item = self.get(file_id)
        if item['status'] == 'ready':
            return item
        if item['upload_until'] <= int(time.time()):
            raise StorageError('This upload has expired. Start a new upload.', 410)
        try:
            head = self.s3.head_object(Bucket=self.bucket, Key=item['object_key'])
        except ClientError as exc:
            if exc.response['Error']['Code'] in ('404', 'NoSuchKey', 'NotFound'):
                raise StorageError('Upload not found in storage. Please upload the file and retry.', 409)
            raise
        if (head['ContentLength'] != item['size'] or head.get('Metadata', {}).get('file-id') != file_id):
            raise StorageError('The stored upload does not match the registered file.', 409)
        version = head.get('VersionId')
        if not version or version == 'null':
            raise StorageError('Enable S3 bucket versioning before uploading files.')
        try:
            self.table.update_item(Key=self.key(file_id),
                UpdateExpression='SET #status = :ready, version_id = :version, etag = :etag',
                ConditionExpression='#status = :uploading', ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={':ready': 'ready', ':uploading': 'uploading', ':version': version, ':etag': head['ETag']})
        except ClientError as exc:
            if exc.response['Error']['Code'] != 'ConditionalCheckFailedException':
                raise
        item = self.get(file_id)
        if item['status'] != 'ready':
            raise StorageError('The file is no longer available.', 409)
        return item

    @aws_errors
    def update(self, file_id, name, description):
        self.get(file_id)
        self.table.update_item(Key=self.key(file_id), UpdateExpression='SET #name = :name, description = :description',
            ConditionExpression='attribute_exists(pk) AND #status <> :deleted',
            ExpressionAttributeNames={'#name': 'name', '#status': 'status'},
            ExpressionAttributeValues={':name': name, ':description': description, ':deleted': 'deleted'})

    @aws_errors
    def delete(self, file_id):
        item = self.get(file_id, include_deleted=True)
        if item['status'] == 'deleted':
            return
        try:
            self.transact([
                ('Update', dict(Key=self.key(file_id), UpdateExpression='SET #status = :deleted',
                    ConditionExpression='#status <> :deleted', ExpressionAttributeNames={'#status': 'status'},
                    ExpressionAttributeValues={':deleted': 'deleted'})),
                ('Update', dict(Key={'pk': self.owner, 'sk': 'USAGE'}, UpdateExpression='ADD files :minus, #size :size',
                    ExpressionAttributeNames={'#size': 'size'}, ExpressionAttributeValues={':minus': -1, ':size': -int(item['size'])}))])
        except ClientError as exc:
            if exc.response['Error']['Code'] != 'TransactionCanceledException':
                raise
            if self.get(file_id, include_deleted=True)['status'] != 'deleted':
                raise

    @aws_errors
    def download(self, file_id, inline=False):
        item = self.get(file_id)
        if item['status'] != 'ready':
            raise StorageError('Verify the upload before downloading it.', 409)
        safe_inline = item['content_type'] in ('application/pdf', 'text/plain', 'image/png', 'image/jpeg',
            'image/gif', 'image/webp', 'audio/mpeg', 'audio/wav', 'audio/ogg', 'video/mp4', 'video/webm')
        disposition = 'inline' if inline and safe_inline else 'attachment'
        return self.s3.generate_presigned_url('get_object', Params={
            'Bucket': self.bucket, 'Key': item['object_key'], 'VersionId': item['version_id'],
            'ResponseContentType': item['content_type'] if safe_inline else 'application/octet-stream',
            'ResponseContentDisposition': disposition + "; filename*=UTF-8''" + quote(item['name'], safe=''),
            'ResponseCacheControl': 'private, no-store'}, ExpiresIn=60)

    @aws_errors
    def purge(self, item):
        """After every upload grant has expired, remove all versions; keep the tombstone."""
        if item['status'] != 'deleted' or int(item.get('upload_until', 0)) + 60 > time.time():
            return False
        for page in self.s3.get_paginator('list_object_versions').paginate(Bucket=self.bucket, Prefix=item['object_key']):
            objects = [{'Key': version['Key'], 'VersionId': version['VersionId']}
                       for kind in ('Versions', 'DeleteMarkers') for version in page.get(kind, [])
                       if version['Key'] == item['object_key']]
            if objects:
                result = self.s3.delete_objects(Bucket=self.bucket, Delete={'Objects': objects, 'Quiet': True})
                if result.get('Errors'):
                    raise StorageError('Some stored versions could not be removed. Retry cleanup.')
        self.table.update_item(Key=self.key(item['file_id']), UpdateExpression='SET purged = :yes',
                               ExpressionAttributeValues={':yes': True})
        return True
