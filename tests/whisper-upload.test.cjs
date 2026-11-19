const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto').webcrypto;

function setup(responses) {
  const elements = {};
  for (const id of ['media-upload', 'media-file', 'media-name', 'media-days', 'media-forever', 'upload-status', 'upload-error', 'upload-progress', 'upload-review', 'upload-submit']) {
    elements['#' + id] = {value: '', disabled: false, hidden: true, handlers: {}, addEventListener(type, fn) { this.handlers[type] = fn; }};
  }
  const form = elements['#media-upload'];
  form.dataset = {register: '/register/', completeTemplate: '/files/FILE_ID/complete/'};
  form.querySelector = () => ({value: 'csrf-test'});
  form.querySelectorAll = () => Object.values(elements).filter(e => e !== form);
  elements['#media-days'].value = '365';
  elements['#media-forever'].checked = false;
  elements['#media-file'].files = [{name: 'meeting.mp3', size: 3, lastModified: 1}];
  const requests = [], uploads = [], payloads = [];
  class FakeFormData { constructor() { this.fields = []; payloads.push(this); } append(...args) { this.fields.push(args); } }
  class XHR {
    constructor() { this.upload = {}; uploads.push(this); }
    open(method, url) { this.method = method; this.url = url; }
    send(data) { this.data = data; this.status = 204; this.upload.onprogress({lengthComputable: true, loaded: 3, total: 3}); this.onload(); }
  }
  const context = {document: {querySelector: id => elements[id], querySelectorAll: () => []}, crypto,
    FormData: FakeFormData, XMLHttpRequest: XHR,
    fetch: async (url, options) => {
      requests.push({url, options});
      const next = responses.shift();
      assert.ok(next, 'unexpected request');
      return {ok: next.status < 400, status: next.status, json: async () => next.body};
    }};
  vm.runInNewContext(fs.readFileSync('dwiest/django/demos/static/dwiest-django-demos/whisper/upload.js', 'utf8'), context);
  return {elements, requests, uploads, payloads, submit: () => form.handlers.submit({preventDefault() {}})};
}
const registration = {status: 200, body: {file: {file_id: 'a'.repeat(32)}, upload: {url: 'https://storage.example.test/', fields: {key: 'uploads/id/source', policy: 'signed-policy'}}}};
const success = {status: 200, body: {detail_url: '/files/id/'}};

test('media bytes go directly to storage and verified result links to review', async () => {
  const run = setup([registration, success]);
  await run.submit();
  assert.equal(run.uploads.length, 1);
  assert.equal(run.uploads[0].url, 'https://storage.example.test/');
  assert.equal(run.payloads[0].fields.at(-1)[0], 'file');
  assert.equal(run.requests.length, 2);
  assert.equal(JSON.parse(run.requests[0].options.body).original_name, 'meeting.mp3');
  assert.equal(run.requests[0].options.headers['X-CSRFToken'], 'csrf-test');
  assert.equal(run.elements['#upload-review'].href, '/files/id/');
  assert.equal(run.elements['#upload-review'].hidden, false);
  assert.equal(run.elements['#upload-progress'].value, 100);
});

test('uncertain verification retries the same operation without uploading bytes again', async () => {
  const run = setup([registration, {status: 503, body: {message: 'Temporary failure'}}, registration, success]);
  await run.submit();
  assert.equal(run.elements['#upload-error'].hidden, false);
  await run.submit();
  assert.equal(run.uploads.length, 1);
  assert.equal(run.requests[0].options.headers['Idempotency-Key'], run.requests[2].options.headers['Idempotency-Key']);
  assert.equal(run.elements['#upload-review'].hidden, false);
});

test('invalid size prevents registration and indefinite retention is explicit null', async () => {
  const run = setup([registration, success]);
  run.elements['#media-file'].files[0].size = 0;
  await run.submit();
  assert.equal(run.requests.length, 0);
  run.elements['#media-file'].files[0].size = 3;
  run.elements['#media-forever'].checked = true;
  await run.submit();
  assert.equal(JSON.parse(run.requests[0].options.body).retention_days, null);
});
