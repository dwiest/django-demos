from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from .ai_credentials import (AIError, SESSION_KEY, api_key_for, encrypt,
                             require_demo_owner, server_session_required)
from .ai_forms import AISettingsForm, AIProposalForm, AnalyzeForm, FIELDS, LABELS, DEFAULT_INSTRUCTIONS
from .ai_models import BookmarkAISettings, BookmarkAIAnalysis
from . import ai_service
from .models import Bookmark, BookmarkTag, Tag
from .ui_views import ROOT, return_url


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
    def page(self, request, form, prefs, error=''):
        return render(request, ROOT + 'ai_settings.html', {
            'form': form, 'ai_error': error, 'nav_section': 'ai',
            'session_key_set': bool(request.session.get(SESSION_KEY)),
            'saved_key_set': bool(prefs.encrypted_api_key),
            'application_instructions': ai_service.APPLICATION_INSTRUCTIONS})

    def get(self, request):
        prefs, _ = BookmarkAISettings.objects.get_or_create(owner=request.user)
        form = AISettingsForm(initial={'instructions': prefs.instructions or DEFAULT_INSTRUCTIONS, 'model': prefs.model})
        return self.page(request, form, prefs)

    @sensitive_variables()
    def post(self, request):
        prefs, _ = BookmarkAISettings.objects.get_or_create(owner=request.user)
        action = request.POST.get('action', 'save')
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
            prefs.save()
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
    prefs, _ = BookmarkAISettings.objects.get_or_create(owner=request.user)
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
        bookmark = Bookmark.objects.filter(pk=review.bookmark_id, owner=review.owner).first()
        if not bookmark or snapshot(bookmark) != review.original['persisted']:
            raise AIError('This bookmark changed after analysis. Open it again and analyze the current version.')


def add_result(review, name, result):
    review.results.append({'tool': name, 'id': result.get('id')})
    review.save(update_fields=['results'])


def assert_available(review, final):
    assert_current(review)
    if Bookmark.objects.filter(url=final['url']).exclude(pk=review.bookmark_id).exists():
        raise AIError('That URL already exists. Open the existing bookmark instead.')


@sensitive_variables()
def apply_proposal(request, review, final):
    """All bookmark/tag writes go through agent-issued, argument-checked MCP calls."""
    user = request.user
    key = api_key_for(request)
    prefs, _ = BookmarkAISettings.objects.get_or_create(owner=user)
    ai_service.mcp_connection_for(user)
    ai_service.model_for(prefs)
    assert_available(review, final)
    # Atomic compare-and-swap, including expiry: double-clicks cannot execute twice.
    if not BookmarkAIAnalysis.objects.filter(pk=review.pk, owner=user, status='pending', expires_at__gt=timezone.now()).update(status='applying', approved=final):
        raise AIError('This proposal has expired or has already been handled.')
    review.status = 'applying'
    review.approved = final
    try:
        assert_current(review)
        if review.bookmark_id:
            changes = {name: final[name] for name in ('url', 'title', 'description', 'article_date', 'status', 'unread')
                       if final[name] != review.original['persisted'][name]}
            if final['tags'] != review.original['persisted']['tags']:
                ids = []
                for title in final['tags']:
                    tag = Tag.objects.filter(owner=user, title__iexact=title).order_by('id').first()
                    if not tag:
                        result = ai_service.execute_call(user, key, prefs, 'create_tag', {'title': title, 'description': None, 'style': ''}, before_approve=lambda: assert_available(review, final))
                        add_result(review, 'create_tag', result)
                        tag = Tag.objects.filter(pk=result.get('id'), owner=user, title=title).first()
                        if not tag:
                            raise AIError('The created tag could not be verified in this application.')
                    ids.append(tag.pk)
                changes['tag_ids'] = ids
            if changes:
                assert_current(review)
                result = ai_service.execute_call(user, key, prefs, 'update_bookmark', {'bookmark_id': review.bookmark_id, 'changes': changes}, before_approve=lambda: assert_available(review, final))
                add_result(review, 'update_bookmark', result)
            bookmark_id = review.bookmark_id
        else:
            arguments = {name: final[name] for name in ('url', 'title', 'description', 'article_date', 'tags')}
            arguments['compact'] = False
            result = ai_service.execute_call(user, key, prefs, 'create_bookmark', arguments, before_approve=lambda: assert_available(review, final))
            add_result(review, 'create_bookmark', result)
            bookmark_id = result.get('id')
            if type(bookmark_id) is not int:
                raise AIError('The created bookmark could not be confirmed.')
            if final['status'] != 0 or final['unread']:
                result = ai_service.execute_call(user, key, prefs, 'update_bookmark', {
                    'bookmark_id': bookmark_id, 'changes': {'status': final['status'], 'unread': final['unread']}})
                add_result(review, 'update_bookmark', result)
        saved = Bookmark.objects.filter(pk=bookmark_id, owner=user).first()
        actual = snapshot(saved) if saved else {}
        expected_tags = {v.casefold() for v in final['tags']}
        actual_tags = {v.casefold() for v in actual.get('tags', [])}
        if any(actual.get(n) != final[n] for n in ('url', 'title', 'description', 'article_date', 'status', 'unread')) or expected_tags != actual_tags:
            raise AIError('The MCP result could not be verified against your approved bookmark. Check the saved data.')
        review.status = 'applied'
        review.bookmark_id = bookmark_id
        review.save(update_fields=['status', 'bookmark_id'])
    except Exception:
        # Never replay an operation after a timeout or partial tag/bookmark write.
        review.status = 'uncertain'
        review.save(update_fields=['status'])
        raise


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
            except Exception:
                review.refresh_from_db()
                return self.page(request, review, form, 'The operation stopped unexpectedly. Check your bookmarks before starting another analysis.')
            messages.success(request, 'Approved bookmark saved through MCP.')
            return HttpResponseRedirect(reverse('demos:bookmarks:bookmark') + '?id=' + str(review.bookmark_id))
        return self.page(request, review, form)
