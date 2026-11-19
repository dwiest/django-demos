from django import forms


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
