"""Apply creation-time consent without replacing user-supplied fields or later edits."""
from types import SimpleNamespace
from django.db import IntegrityError, transaction
from django.utils import timezone
from ..bookmark_ai_models import BookmarkEnrichmentAttempt, BookmarkAIAnalysis
from .ai_credentials import AIError
from .ai_views import apply_proposal, snapshot
from .ai_forms import AIProposalForm


@transaction.atomic
def auto_apply_saved_proposal(attempt, token):
    if not BookmarkEnrichmentAttempt.objects.filter(pk=attempt.pk, lease_token=token).update(updated_at=timezone.now()):
        raise AIError('Another progress check holds this attempt.')
    review = BookmarkAIAnalysis.objects.get(pk=attempt.review_id, owner=attempt.owner)
    if review.status == 'applied':
        return 'applied'
    bookmark = attempt.bookmark
    if not bookmark:
        raise AIError('The bookmark was deleted.')
    current = snapshot(bookmark)
    if current != review.original['persisted']:
        # Retain the proposal but review it against the user's current saved state.
        review.original = {'persisted': current, 'draft': current}
        review.save(update_fields=['original'])
        attempt.analysis['needs_review_reason'] = 'The bookmark changed while enrichment was processing. Review suggestions before applying.'
        return 'ready'
    final = dict(current)
    for name in ('title', 'description', 'article_date'):
        if not final.get(name):
            final[name] = review.proposal.get(name)
    final['tags'] = list(dict.fromkeys(current['tags'] + review.proposal['tags']))
    form = AIProposalForm(dict(final, tags='\n'.join(final['tags'])))
    if not form.is_valid():
        attempt.analysis['needs_review_reason'] = 'Suggestions require review because they exceed bookmark field limits.'
        return 'ready'
    try:
        apply_proposal(SimpleNamespace(user=attempt.owner), review, final)
    except (AIError, IntegrityError):
        attempt.analysis['needs_review_reason'] = 'Automatic approval could not be completed. Review the proposal before applying.'
        return 'ready'
    # Commit bookmark approval and terminal workflow state together, including crash recovery.
    BookmarkEnrichmentAttempt.objects.filter(pk=attempt.pk, lease_token=token).update(status='applied')
    return 'applied'
