"""Additive PWA capture flow. GET drafts; only CSRF-protected POST saves."""
import re
from datetime import datetime, time
from django import forms
from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, reverse
from django.templatetags.static import static
from django.utils.cache import patch_cache_control
from django.utils import timezone
from django.views import View
from .models import Bookmark, BookmarkTag, Tag

ROOT = 'dwiest-django-demos/bookmarks/'
NS = 'demos:bookmarks:'


def shared_url(data):
    validator = forms.URLField(max_length=255)
    for key in ('url', 'text', 'title'):
        value = data.get(key, '')[:8192].strip()
        candidates = [value] + re.findall(r'https?://[^\s<>"\u201c\u201d]+', value)
        for candidate in candidates:
            try:
                result = validator.clean(candidate)
                if result.lower().startswith(('https://', 'http://')):
                    return result
            except forms.ValidationError:
                pass
    return ''


class CaptureForm(forms.Form):
    url = forms.URLField(max_length=255, widget=forms.URLInput(attrs={'class': 'control', 'autofocus': True}))
    title = forms.CharField(max_length=255, required=False, widget=forms.TextInput(attrs={'class': 'control'}))
    article_date = forms.DateField(required=False, label='Publication date', input_formats=['%Y-%m-%d'], widget=forms.DateInput(format='%Y-%m-%d', attrs={'class': 'control', 'type': 'date'}))
    tag_ids = forms.ModelMultipleChoiceField(queryset=Tag.objects.none(), required=False, label='Tags', widget=forms.CheckboxSelectMultiple)
    notes = forms.CharField(required=False, max_length=10000, widget=forms.Textarea(attrs={'class': 'control', 'rows': 3}))

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tag_ids'].queryset = Tag.objects.filter(owner=owner).order_by('title')

    def clean_url(self):
        url = self.cleaned_data['url']
        if not url.lower().startswith(('http://', 'https://')):
            raise forms.ValidationError('Use an HTTP or HTTPS URL.')
        return url


class CaptureView(View):
    def dispatch(self, request, *args, **kwargs):
        if getattr(settings, 'BOOKMARKS_PWA_REQUIRE_LOGIN', True) and not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        response = super().dispatch(request, *args, **kwargs)
        patch_cache_control(response, private=True, no_store=True)
        response['Referrer-Policy'] = 'same-origin'
        return response

    def get(self, request):
        owner = request.user if request.user.is_authenticated else None
        url = shared_url(request.GET)
        title = request.GET.get('title', '')[:255]
        if title == url:
            title = ''
        form = CaptureForm(initial={'url': url, 'title': title}, owner=owner)
        existing = Bookmark.objects.filter(owner=owner, url=url).first() if url else None
        return render(request, ROOT + 'capture.html', {'form': form, 'existing': existing})

    def post(self, request):
        owner = request.user if request.user.is_authenticated else None
        form = CaptureForm(request.POST, owner=owner)
        existing = None
        if form.is_valid():
            data = form.cleaned_data
            existing = Bookmark.objects.filter(owner=owner, url=data['url']).first()
            if not existing:
                article_date = data['article_date']
                if article_date:
                    article_date = datetime.combine(article_date, time.min)
                    if settings.USE_TZ:
                        article_date = timezone.make_aware(article_date, timezone.get_current_timezone())
                try:
                    with transaction.atomic():
                        bookmark = Bookmark.objects.create(owner=owner, url=data['url'], title=data['title'], description=data['notes'], article_date=article_date, unread=True, status=0)
                        for tag in data['tag_ids']:
                            BookmarkTag.objects.create(owner=owner, bookmark=bookmark, tag=tag)
                except IntegrityError:
                    existing = Bookmark.objects.filter(owner=owner, url=data['url']).first()
                    if not existing:
                        form.add_error('url', 'This URL could not be saved. It may already be registered.')
                else:
                    return render(request, ROOT + 'capture.html', {'saved': bookmark})
        return render(request, ROOT + 'capture.html', {'form': form, 'existing': existing})


def manifest(request):
    home = reverse(NS + 'home')
    return JsonResponse({'id': home, 'name': 'Wiest Bookmarks', 'short_name': 'Bookmarks', 'start_url': home, 'scope': home, 'display': 'standalone', 'theme_color': '#182d35', 'background_color': '#f7f6f2', 'icons': [{'src': static('bookmarks/icon-%s.png' % size), 'sizes': '%sx%s' % (size, size), 'type': 'image/png', 'purpose': 'any'} for size in (192, 512)], 'share_target': {'action': reverse(NS + 'capture'), 'method': 'GET', 'params': {'title': 'title', 'text': 'text', 'url': 'url'}}}, content_type='application/manifest+json')


def service_worker(request):
    # No caches: authenticated pages and shared URLs stay on the network.
    response = HttpResponse("self.addEventListener('install', e => self.skipWaiting());\nself.addEventListener('activate', e => e.waitUntil(self.clients.claim()));\n", content_type='application/javascript')
    response['Cache-Control'] = 'no-cache'
    return response
