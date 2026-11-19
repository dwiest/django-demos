from django import forms
from django.conf import settings
import os


class FileForm(forms.Form):
    display_name = forms.CharField(max_length=255, label='Display name')
    keep_indefinitely = forms.BooleanField(required=False, label='Keep indefinitely')
    retention_days = forms.IntegerField(required=False, min_value=1, max_value=36500,
        label='Days to keep from upload completion', initial=365)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'control'

    def clean(self):
        data = super().clean()
        if data.get('keep_indefinitely'):
            data['retention_days'] = None
        elif data.get('retention_days') is None:
            self.add_error('retention_days', 'Enter retention days or choose Keep indefinitely.')
        return data


class TranscriptionForm(forms.Form):
    operation_key = forms.RegexField(regex=r'^[a-f0-9]{32}$', widget=forms.HiddenInput)
    model = forms.ChoiceField(choices=[(name, name) for name in (
        'tiny', 'tiny.en', 'base', 'base.en', 'small', 'small.en', 'medium', 'medium.en',
        'large', 'large-v1', 'large-v2', 'large-v3', 'turbo')], initial='base')
    language = forms.CharField(required=False, max_length=5, label='Language code',
        help_text='Leave blank to detect automatically, or use a Whisper language code such as en, es, fr or ja.')
    task = forms.ChoiceField(choices=[('transcribe', 'Transcribe in the spoken language'),
                                    ('translate', 'Translate speech into English')], initial='transcribe')
    word_timestamps = forms.BooleanField(required=False, label='Include word timestamps')
    temperature = forms.FloatField(min_value=0, max_value=1, initial=0,
        widget=forms.NumberInput(attrs={'step': '0.1'}))
    beam_size = forms.IntegerField(min_value=1, max_value=10, initial=5,
        help_text='Beam search applies when temperature is zero.')
    condition_on_previous_text = forms.BooleanField(required=False, initial=True, label='Use previous text as context')
    initial_prompt = forms.CharField(required=False, max_length=2000, widget=forms.Textarea(attrs={'rows': 4}),
        label='Vocabulary or initial context', help_text='Names, specialized terms or sample phrasing for Whisper. Analysis instructions come in phase 3.')
    keep_indefinitely = forms.BooleanField(required=False, label='Keep this job and its outputs indefinitely')
    retention_days = forms.IntegerField(required=False, min_value=1, max_value=36500, initial=365,
        label='Days to keep after the job finishes')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, (forms.CheckboxInput, forms.HiddenInput)):
                field.widget.attrs['class'] = 'control'

    def clean(self):
        data = super().clean()
        model, language = data.get('model', ''), data.get('language', '').lower().strip()
        data['language'] = language
        if data.get('task') == 'translate' and (model == 'turbo' or model.endswith('.en')):
            self.add_error('model', 'Translation needs a multilingual model other than turbo.')
        if model.endswith('.en') and language not in ('', 'en'):
            self.add_error('language', 'English-only models require English audio.')
        if data.get('keep_indefinitely'):
            data['retention_days'] = None
        elif data.get('retention_days') is None:
            self.add_error('retention_days', 'Choose retention days or Keep indefinitely.')
        return data

    def payload(self, file_id):
        names = ('model', 'language', 'task', 'word_timestamps', 'temperature', 'beam_size',
                 'condition_on_previous_text', 'initial_prompt')
        return {'file_id': file_id, 'options': {name: self.cleaned_data[name] for name in names},
                'retention_days': self.cleaned_data['retention_days']}


class AISettingsForm(forms.Form):
    model_choice = forms.ChoiceField(required=False, label='Suggested model')
    model = forms.RegexField(regex=r'^[A-Za-z0-9._:-]{1,128}$', required=False, max_length=128,
        label='Custom model (optional)', help_text='Overrides the dropdown. Enter an exact model ID available to your API account.')
    instructions = forms.CharField(required=False, max_length=8000, label='Default analysis instructions',
        widget=forms.Textarea(attrs={'rows': 7}))
    api_key = forms.CharField(required=False, max_length=512, strip=True,
        label='OpenAI API key', widget=forms.PasswordInput(attrs={'autocomplete': 'off'}),
        help_text='Leave blank to keep the saved key. Saved keys are never displayed.')
    remove_api_key = forms.BooleanField(required=False, label='Remove my saved API key')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        models = getattr(settings, 'WHISPER_AI_MODELS', os.environ.get('WHISPER_AI_MODELS',
            getattr(settings, 'BOOKMARKS_AI_MODELS', os.environ.get('BOOKMARKS_AI_MODELS',
            ['gpt-6.1-sol', 'gpt-6.1-terra', 'gpt-6-luna', 'gpt-5.4-mini']))))
        if isinstance(models,str): models=[m.strip() for m in models.split(',') if m.strip()]
        self.fields['model_choice'].choices=[('', 'Choose a model')] + [(m,m) for m in dict.fromkeys(models)]
        saved=self.initial.get('model','')
        if not self.is_bound and saved in models:
            self.initial['model_choice']=saved
            self.initial['model']=''
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'control'

    def clean(self):
        data = super().clean()
        data['model'] = data.get('model') or data.get('model_choice','')
        if data.get('api_key') and data.get('remove_api_key'):
            self.add_error('api_key', 'Replace or remove the key, not both.')
        return data


class AnalysisForm(forms.Form):
    operation_key = forms.RegexField(regex=r'^[a-f0-9]{32}$',widget=forms.HiddenInput)
    instructions = forms.CharField(required=False,max_length=4000,label='Instructions for this analysis',
        widget=forms.Textarea(attrs={'class':'control','rows':4}))
    retention_days = forms.IntegerField(min_value=1,max_value=36500,initial=365,label='Days to keep the analysis',widget=forms.NumberInput(attrs={'class':'control'}))


class AnalysisReviewForm(forms.Form):
    title=forms.CharField(max_length=255)
    summary=forms.CharField(max_length=20000,required=False,widget=forms.Textarea(attrs={'rows':6}))
    key_points=forms.CharField(required=False,widget=forms.Textarea(attrs={'rows':4}))
    decisions=forms.CharField(required=False,widget=forms.Textarea(attrs={'rows':4}))
    action_items=forms.CharField(required=False,widget=forms.Textarea(attrs={'rows':4}))
    open_questions=forms.CharField(required=False,widget=forms.Textarea(attrs={'rows':4}))
    warnings=forms.CharField(required=False,widget=forms.Textarea(attrs={'rows':4}))

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        for name,field in self.fields.items():
            field.widget.attrs['class']='control'
            if name not in ('title','summary'):field.help_text='One item per line; up to 30 items, 2000 characters each.'

    def clean(self):
        data=super().clean()
        for name in ('key_points','decisions','action_items','open_questions','warnings'):
            lines=[line.strip() for line in data.get(name,'').splitlines() if line.strip()]
            if len(lines)>30 or any(len(line)>2000 for line in lines):self.add_error(name,'Use at most 30 items of 2000 characters each.')
            else:data[name]=lines
        return data
