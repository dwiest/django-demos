from datetime import datetime

from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase

from .models import Journal, JournalEntry
from .views import JournalEntryEditView, JournalView


class JournalFlowTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create(username='journal-test')
        self.journal = Journal.objects.create(owner=self.owner, name='Daily notes')
        self.entry = JournalEntry.objects.create(
            owner=self.owner, journal=self.journal,
            date=datetime(2026, 12, 1), content='First entry')
        other = Journal.objects.create(owner=self.owner, name='Other notes')
        JournalEntry.objects.create(
            owner=self.owner, journal=other,
            date=datetime(2026, 12, 2), content='Other journal entry')
        self.factory = RequestFactory()

    def request(self, method, data):
        request = getattr(self.factory, method)('/', data)
        request.user = self.owner
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def test_entries_belong_to_selected_journal(self):
        view = JournalView()
        view.setup(self.request('get', {'id': self.journal.id, 'filter': 'none'}))
        self.assertEqual(list(view.get_queryset()), [self.entry])

    def test_december_date_filter(self):
        view = JournalView()
        view.setup(self.request('get', {
            'id': self.journal.id, 'filter': 'date', 'month': 12, 'year': 2026}))
        self.assertEqual(list(view.get_queryset()), [self.entry])

    def test_date_filter_requires_year(self):
        view = JournalView()
        view.setup(self.request('get', {
            'id': self.journal.id, 'filter': 'date', 'month': 12}))
        self.assertFalse(view.filter.is_valid())
        self.assertIn('year', view.filter.errors)

    def test_invalid_entry_preserves_draft_and_journal(self):
        response = JournalEntryEditView.as_view()(self.request('post', {
            'journal': self.journal.id, 'date': 'bad',
            'content': 'Keep this draft', 'status': 0}))
        self.assertContains(response, 'Keep this draft')
        self.assertContains(response, 'Enter a valid date')
        self.assertContains(response, 'name="journal" value="%s"' % self.journal.id)

    def test_create_entry_returns_to_its_journal(self):
        response = JournalEntryEditView.as_view()(self.request('post', {
            'journal': self.journal.id, 'date': '2026-11-08',
            'content': 'Saved entry', 'status': 0}))
        self.assertEqual(response.status_code, 302)
        saved = JournalEntry.objects.get(content='Saved entry')
        self.assertEqual(saved.journal_id, self.journal.id)
