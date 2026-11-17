from unittest.mock import patch
from datetime import datetime
from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse
from django.template.loader import render_to_string
from . import test_enrichment as fixtures
from .test_enrichment import BASE, URL, ANALYSIS
from .enrichment import start
from .job_status import decorate, filter_state
from .models import Bookmark
from ..bookmark_ai_models import BookmarkEnrichmentAttempt


@override_settings(BOOKMARKS_JOB_SERVICE_URL=BASE)
class ListPresentationTests(TestCase):
    setUp = fixtures.EnrichmentTests.setUp

    def test_download_failure_without_analysis_is_not_available_and_filter_matches(self):
        for mode in ('download', 'analyze'):
            attempt = start(self.user, self.bookmark, self.original, URL, mode=mode)
            attempt.status = 'failed'; attempt.retrieval = {'retrieved': False}; attempt.save()
            decorate([self.bookmark], self.user)
            self.assertEqual(self.bookmark.analysis_state, 'not_available')
            matches = filter_state(Bookmark.objects.filter(owner=self.user), self.user, analysis='not_available')
            self.assertEqual(list(matches.values_list('pk', flat=True)), [self.bookmark.pk])
            self.assertFalse(filter_state(Bookmark.objects.filter(owner=self.user), self.user, analysis='not_requested').exists())
        page = self.client.get(reverse('demos:bookmarks:home'))
        self.assertContains(page, 'Analysis: Not available')
        attempt.analysis_job_id = ANALYSIS; attempt.retrieval = {'retrieved': True}; attempt.save()
        decorate([self.bookmark], self.user)
        self.assertEqual(self.bookmark.analysis_state, 'failed')

    def test_tags_actions_and_badges_follow_description(self):
        response = self.client.get(reverse('demos:bookmarks:home'))
        text = response.content.decode()
        row = text[text.index('<article class="bookmark-row"'):text.index('</article>')]
        self.assertLess(row.index('class="description"'), row.index('class="bookmark-footer"'))
        self.assertLess(row.index('class="tags"'), row.index('class="row-actions"'))
        self.assertLess(row.index('class="row-actions"'), row.index('class="job-badges"'))


class MonthHeaderTests(SimpleTestCase):
    def render(self, month):
        return render_to_string('dwiest-django-demos/bookmarks/components/month_header.html',
            __import__('dwiest.django.demos.templatetags.bookmark_records', fromlist=['month_header']).month_header(datetime(2026, month, 1)))

    def test_seasonal_defaults_and_custom_safe_image(self):
        self.assertIn('🎃', self.render(10)); self.assertIn('🦃', self.render(11)); self.assertIn('🎄 🎁', self.render(12))
        with override_settings(BOOKMARKS_MONTH_HEADERS={11: {'icon': '🍁', 'image_url': '/static/month.jpg'}}):
            rendered = self.render(11)
            self.assertIn('/static/month.jpg', rendered); self.assertIn('November 2026', rendered)
        for image in ['javascript:alert(1)', '//untrusted.example/image', '/\\untrusted.example/image', 'https://user:secret@example.com/image']:
            with override_settings(BOOKMARKS_MONTH_HEADERS={11: {'image_url': image}}):
                self.assertNotIn('<img', self.render(11))
