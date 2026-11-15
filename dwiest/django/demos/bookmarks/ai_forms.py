from django import forms
from .ai_credentials import configured
from .ai_sites import normalize_site

FIELDS = ('url', 'title', 'description', 'article_date', 'tags')
LABELS = {'url': 'URL', 'title': 'Title', 'description': 'Description', 'article_date': 'Publication date', 'tags': 'Tags'}
DEFAULT_INSTRUCTIONS = ('Preserve the original article title. Summarize the first paragraph concisely and factually. '
                        'Reuse existing tags and prefer specific technical tags when appropriate.')


class StyledForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'control')


class AISettingsForm(StyledForm):
    api_key = forms.CharField(required=False, max_length=512, strip=True,
                              widget=forms.PasswordInput(attrs={'autocomplete': 'off'}), label='OpenAI API key')
    storage = forms.ChoiceField(choices=(('session', 'Use for this session'), ('saved', 'Save encrypted')), initial='session')
    model = forms.ChoiceField(required=False)
    instructions = forms.CharField(required=False, max_length=8000, widget=forms.Textarea(attrs={'rows': 7}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        models = configured('BOOKMARKS_AI_MODELS', [])
        if isinstance(models, str):
            models = [m.strip() for m in models.split(',') if m.strip()]
        default = configured('BOOKMARKS_AI_MODEL')
        self.fields['model'].choices = [('', 'Application default' + (' (' + default + ')' if default else ' — not configured'))] + [(m, m) for m in models]


class AISiteBlacklistForm(StyledForm):
    blocked_domains = forms.CharField(
        required=False, max_length=26000, label='Blacklisted sites',
        widget=forms.Textarea(attrs={'rows': 6, 'placeholder': 'politico.eu\nhollywoodreporter.com\nmsn.com'}),
        help_text='One domain per line, or paste a full article URL. Each entry includes its subdomains. Remove a line to stop warnings for that site. Maximum 100 sites.')

    def clean_blocked_domains(self):
        domains = []
        for line_number, line in enumerate(self.cleaned_data['blocked_domains'].splitlines(), 1):
            if not line.strip():
                continue
            try:
                domain = normalize_site(line)
            except ValueError as exc:
                raise forms.ValidationError('Line {}: {}'.format(line_number, exc))
            if domain not in domains:
                domains.append(domain)
        if len(domains) > 100:
            raise forms.ValidationError('Choose at most 100 sites.')
        return domains


class AnalyzeForm(StyledForm):
    url = forms.URLField(max_length=255)
    instructions = forms.CharField(required=False, max_length=4000)

    def clean_url(self):
        url = self.cleaned_data['url']
        if not url.lower().startswith(('https://', 'http://')):
            raise forms.ValidationError('Use an HTTP or HTTPS article URL.')
        return url


class AIProposalForm(StyledForm):
    url = forms.URLField(max_length=255, label='URL')
    title = forms.CharField(max_length=255)
    description = forms.CharField(required=False, max_length=20000, widget=forms.Textarea(attrs={'rows': 7}))
    article_date = forms.DateField(required=False, label='Publication date', input_formats=['%Y-%m-%d'], widget=forms.DateInput(attrs={'type': 'date'}))
    tags = forms.CharField(required=False, max_length=8000, widget=forms.Textarea(attrs={'rows': 4}), help_text='One tag per line. New tags are created only when you approve.')
    selected = forms.MultipleChoiceField(choices=[(n, LABELS[n]) for n in FIELDS], required=False, widget=forms.CheckboxSelectMultiple)

    clean_url = AnalyzeForm.clean_url

    def clean_tags(self):
        tags = []
        seen = set()
        for value in self.cleaned_data['tags'].splitlines():
            value = value.strip()
            if not value:
                continue
            if len(value) > 255:
                raise forms.ValidationError('Tag names must be 255 characters or fewer.')
            if value.casefold() not in seen:
                tags.append(value)
                seen.add(value.casefold())
        if len(tags) > 30:
            raise forms.ValidationError('Choose at most 30 tags.')
        return tags

    def proposal(self):
        data = {name: self.cleaned_data[name] for name in FIELDS}
        data['article_date'] = data['article_date'].isoformat() if data['article_date'] else None
        return data
