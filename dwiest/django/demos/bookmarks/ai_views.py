from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.db import IntegrityError, transaction
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from .ai_credentials import (AIError, SESSION_KEY, api_key_for, encrypt,
                             require_demo_owner, server_session_required)
from .ai_forms import AISettingsForm, AIProposalForm, AISiteBlacklistForm, AnalyzeForm, FIELDS, LABELS, DEFAULT_INSTRUCTIONS
from .ai_sites import blacklisted_site
from ..bookmark_ai_models import BookmarkAISettings, BookmarkAIAnalysis
from . import ai_service
from .models import Bookmark, BookmarkTag, Tag
from .ui_views import ROOT, return_url
from .ui_forms import BookmarkEditorForm


def snapshot(bookmark):
    return {'url': bookmark.url or '', 'title': bookmark.title or '',
            'description': bookmark.description or '',
            'article_date': bookmark.article_date.strftime('%Y-%m-%d') if bookmark.article_date else None,
            'tags': list(Tag.objects.filter(owner=bookmark.owner, bookmarktag__bookmark=bookmark).order_by('title', 'id').values_list('title', flat=True).distinct()) if bookmark.pk else [],
            'tag_ids': list(BookmarkTag.objects.filter(owner=bookmark.owner, bookmark=bookmark).order_by('tag_id').values_list('tag_id', flat=True)) if bookmark.pk else [],
            'status': bookmark.status, 'unread': bookmark.unread,
            'version': bookmark.last_modified.isoformat() if bookmark.pk else None}


@method_decorator(never_cache, name='dispatch')
class AIProtectedView(View):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        try:
            require_demo_owner(request.user)
        except AIError as exc:
            return HttpResponseForbidden(str(exc))
        return super().dispatch(request, *args, **kwargs)


@method_decorator(sensitive_post_parameters('api_key'), name='dispatch')
class AISettingsView(AIProtectedView):
    def page(self, request, form, prefs, error='', blacklist_form=None, job_form=None):
        from .ai_forms import JobServiceSettingsForm
        from .ai_credentials import configured
        job_form = job_form if job_form is not None else JobServiceSettingsForm(initial={
            'use_job_service': prefs.use_job_service, 'include_raw_html': prefs.include_raw_html,
            'keep_indefinitely': prefs.job_retention_days is None, 'job_retention_days': prefs.job_retention_days})
        return render(request, ROOT + 'ai_settings.html', {
            'form': form, 'job_form': job_form, 'job_service_url': configured('BOOKMARKS_JOB_SERVICE_URL', ''), 'ai_error': error, 'nav_section': 'ai',
            'session_key_set': bool(request.session.get(SESSION_KEY)),
            'saved_key_set': bool(prefs.encrypted_api_key),
            'blacklist_form': blacklist_form if blacklist_form is not None else AISiteBlacklistForm(initial={'blocked_domains': '\n'.join(prefs.blocked_domains)}),
            'application_instructions': ai_service.APPLICATION_INSTRUCTIONS})

    def get(self, request):
        prefs, _ = BookmarkAISettings.objects.get_or_create(owner=request.user)
        form = AISettingsForm(initial={'instructions': prefs.instructions or DEFAULT_INSTRUCTIONS, 'model': prefs.model})
        return self.page(request, form, prefs)

    @sensitive_variables()
    def post(self, request):
        prefs, _ = BookmarkAISettings.objects.get_or_create(owner=request.user)
        action = request.POST.get('action', 'save')
        if action == 'save_job_service':
            from .ai_forms import JobServiceSettingsForm
            from .job_client import JobClient
            job_form = JobServiceSettingsForm(request.POST)
            form = AISettingsForm(initial={'instructions': prefs.instructions or DEFAULT_INSTRUCTIONS, 'model': prefs.model})
            if job_form.is_valid():
                try:
                    if job_form.cleaned_data['use_job_service']:
                        JobClient(request.user).request('POST', '/retention', {'days': job_form.cleaned_data['job_retention_days']})
                    for name in ('use_job_service', 'include_raw_html', 'job_retention_days'):
                        setattr(prefs, name, job_form.cleaned_data[name])
                    prefs.save(update_fields=['use_job_service', 'include_raw_html', 'job_retention_days'])
                except AIError as exc:
                    return self.page(request, form, prefs, str(exc), job_form=job_form)
                messages.success(request, 'URL retrieval settings saved. Retention changes apply to new service jobs.')
                return HttpResponseRedirect(reverse('demos:bookmarks:ai_settings') + '#url-retrieval')
            return self.page(request, form, prefs, job_form=job_form)
        if action == 'save_blacklist':
            blacklist_form = AISiteBlacklistForm(request.POST)
            if not blacklist_form.is_valid():
                form = AISettingsForm(initial={'instructions': prefs.instructions or DEFAULT_INSTRUCTIONS, 'model': prefs.model})
                return self.page(request, form, prefs, blacklist_form=blacklist_form)
            prefs.blocked_domains = blacklist_form.cleaned_data['blocked_domains']
            prefs.save(update_fields=['blocked_domains'])
            messages.success(request, 'AI site blacklist saved.')
            return HttpResponseRedirect(reverse('demos:bookmarks:ai_settings') + '#site-blacklist')
        if action == 'remove':
            request.session.pop(SESSION_KEY, None)
            prefs.encrypted_api_key = ''
            prefs.save(update_fields=['encrypted_api_key'])
            messages.success(request, 'OpenAI API credentials removed.')
            return HttpResponseRedirect(reverse('demos:bookmarks:ai_settings'))
        if action == 'reset':
            prefs.instructions = DEFAULT_INSTRUCTIONS
            prefs.save(update_fields=['instructions'])
            messages.success(request, 'AI instructions reset to defaults.')
            return HttpResponseRedirect(reverse('demos:bookmarks:ai_settings'))
        form = AISettingsForm(request.POST)
        if not form.is_valid():
            return self.page(request, form, prefs)
        try:
            key = form.cleaned_data['api_key']
            if action == 'test':
                key = key or api_key_for(request)
                ai_service.openai_request(key, model=True)
                messages.success(request, 'OpenAI accepted the API key. Model tools and MCP will be checked during Analyze.')
                # Never reflect the submitted key into the returned form or HTML.
                return self.page(request, form, prefs)
            if key:
                if form.cleaned_data['storage'] == 'session':
                    server_session_required()
                    request.session[SESSION_KEY] = encrypt(key)
                    request.session.set_expiry(0)
                else:
                    prefs.encrypted_api_key = encrypt(key)
                    request.session.pop(SESSION_KEY, None)
            prefs.instructions = form.cleaned_data['instructions']
            prefs.model = form.cleaned_data['model']
            prefs.save(update_fields=['encrypted_api_key', 'instructions', 'model'])
        except AIError as exc:
            return self.page(request, form, prefs, str(exc))
        messages.success(request, 'AI settings saved.')
        return HttpResponseRedirect(reverse('demos:bookmarks:ai_settings'))


@sensitive_variables()
def start_analysis(request, bookmark):
    """Called by the existing editor POST; normal Save remains the existing path."""
    require_demo_owner(request.user)
    form = AnalyzeForm({'url': request.POST.get('url'), 'instructions': request.POST.get('ai_instructions', '')})
    if not form.is_valid():
        raise AIError('Enter a valid HTTP or HTTPS URL and instructions of at most 4,000 characters.')
    prefs, _ = BookmarkAISettings.objects.get_or_create(owner=request.user)
    if request.POST.get('action') == 'job_download' and not prefs.use_job_service:
        raise AIError('Enable the job service in AI settings before downloading a page.')
    listed = blacklisted_site(form.cleaned_data['url'], prefs.blocked_domains)
    if listed:
        messages.warning(request, '{} is on your AI site blacklist. Analysis is being attempted at your request.'.format(listed))
    original = snapshot(bookmark)
    draft = dict(original)
    for field in ('url', 'title', 'description', 'article_date'):
        if field in request.POST:
            draft[field] = request.POST[field] or (None if field == 'article_date' else '')
    tag_ids = request.POST.getlist('tag_ids')
    try:
        tag_ids = [int(v) for v in tag_ids]
        status = int(request.POST.get('status', original['status']))
        if status not in (-1, 0, 1):
            raise ValueError()
    except (TypeError, ValueError):
        raise AIError('The current bookmark form contains invalid values.') from None
    tags = list(Tag.objects.filter(owner=request.user, pk__in=tag_ids).order_by('title', 'id'))
    if len(tags) != len(set(tag_ids)):
        raise AIError('One or more selected tags are unavailable.')
    draft.update(tags=[t.title for t in tags], status=status, unread='unread' in request.POST)
    if prefs.use_job_service:
        if form.cleaned_data['instructions']:
            raise AIError('The job service uses bookmark.enrichment.v1. Per-analysis custom instructions apply only to direct AI analysis.')
        from .enrichment import start
        mode = 'download' if request.POST.get('action') == 'job_download' else 'analyze'
        attempt = start(request.user, bookmark, {'persisted': original, 'draft': draft}, form.cleaned_data['url'], mode=mode)
        return HttpResponseRedirect(reverse('demos:bookmarks:enrichment', args=[attempt.pk]))
    proposal, sources = ai_service.analyze(request.user, api_key_for(request), prefs,
        form.cleaned_data['url'], bookmark.pk, form.cleaned_data['instructions'])
    review = BookmarkAIAnalysis.objects.create(owner=request.user, bookmark_id=bookmark.pk,
        original={'persisted': original, 'draft': draft}, proposal=proposal,
        sources=sources, expires_at=timezone.now() + timedelta(minutes=30))
    return HttpResponseRedirect(reverse('demos:bookmarks:ai_review', args=[review.pk]))


def proposal_initial(review):
    values = dict(review.proposal)
    values['tags'] = '\n'.join(values['tags'])
    values['selected'] = list(FIELDS)
    return values


def effective_proposal(review, form):
    final = dict(review.original['draft'])
    proposed = form.proposal()
    for name in form.cleaned_data['selected']:
        final[name] = proposed[name]
    # Validate the complete merged data, including fields kept from the editor.
    merged = dict(final, tags='\n'.join(final['tags']))
    validation = AIProposalForm(merged)
    if not validation.is_valid():
        raise AIError('The final bookmark contains invalid values. Select or correct the proposed fields.')
    final.update(validation.proposal())
    return final


def assert_current(review):
    if review.bookmark_id:
        bookmark = Bookmark.objects.select_for_update().filter(pk=review.bookmark_id, owner=review.owner).first()
        if not bookmark or snapshot(bookmark) != review.original['persisted']:
            raise AIError('This bookmark changed after analysis. Open it again and analyze the current version.')
        return bookmark
    return Bookmark(owner=review.owner)


@transaction.atomic
def apply_proposal(request, review, final):
    """Save approved values locally, including review consumption, in one transaction."""
    user = request.user
    require_demo_owner(user)
    # Claim before reading/writing bookmark state. A failed save rolls this back
    # with its tags/assignments; a committed review cannot execute twice.
    if not BookmarkAIAnalysis.objects.filter(pk=review.pk, owner=user, status='pending', expires_at__gt=timezone.now()).update(status='applying'):
        raise AIError('This proposal has expired or has already been handled.')
    bookmark = assert_current(review)
    if Bookmark.objects.filter(url=final['url']).exclude(pk=review.bookmark_id).exists():
        raise AIError('That URL already exists. Open the existing bookmark instead.')

    tag_ids = []
    for title in final['tags']:
        tag = Tag.objects.filter(owner=user, title__iexact=title).order_by('id').first()
        if not tag:
            tag = Tag.objects.create(owner=user, title=title, description=None, style='')
        tag_ids.append(tag.pk)

    # Use the same ModelForm as manual saves for model validation, dates, and
    # owner-scoped tag choices. All values come from the merged review form.
    form = BookmarkEditorForm(dict(final, tag_ids=tag_ids), instance=bookmark, owner=user)
    if not form.is_valid():
        raise AIError('The approved bookmark could not be validated. Check its values and URL; no changes were saved.')
    new = not bookmark.pk
    saved = form.save(commit=False)
    saved.owner = user
    if new:
        saved.save()
    else:
        changed = [name for name in ('url', 'title', 'description', 'article_date', 'status', 'unread')
                   if final[name] != review.original['persisted'][name]]
        if final['tags'] != review.original['persisted']['tags'] or changed:
            # Preserve unchanged fields, including legacy publication timestamps.
            saved.save(update_fields=changed + ['last_modified'])
    BookmarkTag.objects.filter(owner=user, bookmark=saved).exclude(tag_id__in=tag_ids).delete()
    for tag_id in tag_ids:
        BookmarkTag.objects.get_or_create(owner=user, bookmark=saved, tag_id=tag_id)
    review.status = 'applied'
    review.approved = final
    review.bookmark_id = saved.pk
    review.save(update_fields=['status', 'approved', 'bookmark_id'])


class AIReviewView(AIProtectedView):
    def record(self, request, analysis_id):
        return get_object_or_404(BookmarkAIAnalysis, pk=analysis_id, owner=request.user)

    def page(self, request, review, form, error=''):
        rows = [{'name': name, 'label': LABELS[name], 'before': review.original['draft'][name], 'field': form[name]}
                for name in FIELDS]
        if review.status == 'pending' and review.expires_at <= timezone.now():
            review.status = 'expired'
        response = render(request, ROOT + 'ai_review.html', {
            'review': review, 'form': form, 'rows': rows, 'ai_error': error,
            'preserved': review.original['draft'], 'selected_fields': form['selected'].value() or []})
        return response

    def get(self, request, analysis_id):
        review = self.record(request, analysis_id)
        return self.page(request, review, AIProposalForm(initial=proposal_initial(review)))

    @sensitive_variables()
    def post(self, request, analysis_id):
        review = self.record(request, analysis_id)
        form = AIProposalForm(request.POST)
        if request.POST.get('action') == 'cancel':
            BookmarkAIAnalysis.objects.filter(pk=review.pk, owner=request.user, status='pending').update(status='cancelled')
            return HttpResponseRedirect(reverse('demos:bookmarks:home'))
        if review.status != 'pending' or review.expires_at <= timezone.now():
            return self.page(request, review, form, 'This proposal has expired or has already been handled.')
        if form.is_valid():
            try:
                final = effective_proposal(review, form)
                apply_proposal(request, review, final)
            except AIError as exc:
                review.refresh_from_db()
                return self.page(request, review, form, str(exc))
            except IntegrityError:
                review.refresh_from_db()
                return self.page(request, review, form, 'Could not save this bookmark. Its URL may already exist. No changes were saved.')
            except Exception:
                review.refresh_from_db()
                return self.page(request, review, form, 'The bookmark could not be saved. No changes were saved; you can try again.')
            messages.success(request, 'Approved bookmark saved.')
            return HttpResponseRedirect(reverse('demos:bookmarks:bookmark') + '?id=' + str(review.bookmark_id))
        return self.page(request, review, form)
