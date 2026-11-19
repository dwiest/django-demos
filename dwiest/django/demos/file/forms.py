from django import forms


class FileDetailsForm(forms.Form):
    name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={'class': 'file-name'}))
    description = forms.CharField(required=False, max_length=10000,
                                  widget=forms.Textarea(attrs={'rows': 5}))

    def clean_name(self):
        value = self.cleaned_data['name']
        if any(ord(c) < 32 for c in value):
            raise forms.ValidationError('The filename cannot contain control characters.')
        return value
