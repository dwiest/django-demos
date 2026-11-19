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
