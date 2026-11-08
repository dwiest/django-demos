"""Browser forms, independent of the legacy forms and REST contract."""
import calendar
from django import forms
from .models import Bookmark, Tag
from .ui_tags import PALETTE, tag_tone


class TagCheckboxWidget(forms.CheckboxSelectMultiple):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if hasattr(value, "instance"):
            option["attrs"]["data-tone"] = tag_tone(value.instance)
        return option



class BookmarkEditorForm(forms.ModelForm):
    url = forms.URLField(max_length=255, label='URL')
    title = forms.CharField(max_length=255, required=False)
    tag_ids = forms.ModelMultipleChoiceField(queryset=Tag.objects.none(), required=False, label='Tags', widget=TagCheckboxWidget)
    status = forms.TypedChoiceField(coerce=int, choices=((0, 'Active'), (1, 'Hidden'), (-1, 'Deleted')))

    class Meta:
        model = Bookmark
        fields = ('url', 'title', 'description', 'article_date', 'unread', 'status')
        widgets = {'description': forms.Textarea(attrs={'rows': 8}), 'article_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'})}
        labels = {'article_date': 'Publication date'}

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tag_ids'].queryset = Tag.objects.filter(owner=owner).order_by('title')
        if self.instance.pk and not self.is_bound:
            self.initial['tag_ids'] = list(self.instance.bookmarktag_set.filter(owner=owner).values_list('tag_id', flat=True))
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'control')


class BookmarkQueryForm(forms.Form):
    term = forms.CharField(required=False, max_length=255)
    field = forms.ChoiceField(required=False, choices=(('all', 'All fields'), ('title', 'Title'), ('description', 'Description'), ('url', 'URL')))
    filter = forms.ChoiceField(required=False, choices=(('none', 'All dates and titles'), ('undated', 'Undated'), ('untitled', 'Untitled'), ('date', 'Publication date')))
    month = forms.TypedChoiceField(required=False, coerce=int, empty_value=None, choices=[('', 'All months')] + [(i, calendar.month_name[i]) for i in range(1, 13)])
    year = forms.IntegerField(required=False, min_value=1, max_value=9999)
    tag_id = forms.ModelMultipleChoiceField(queryset=Tag.objects.none(), required=False, label='Tags', widget=forms.CheckboxSelectMultiple)
    show_hidden = forms.BooleanField(required=False)
    show_deleted = forms.BooleanField(required=False)
    deleted_only = forms.BooleanField(required=False, label='Deleted only')
    hide_read = forms.BooleanField(required=False, label='Unread only')
    page_size = forms.TypedChoiceField(required=False, coerce=int, empty_value=40, choices=((20, '20 per page'), (40, '40 per page'), (100, '100 per page')))

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tag_id'].queryset = Tag.objects.filter(owner=owner).order_by('title')
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'control')
        self.fields['term'].widget.attrs.update(placeholder='Search bookmarks…', **{'aria-label': 'Search bookmarks'})
        self.fields['field'].widget.attrs['aria-label'] = 'Search field'
        self.fields['page_size'].widget.attrs['aria-label'] = 'Bookmarks per page'

    def clean(self):
        data = super().clean()
        if data.get('filter') == 'date' and not data.get('year'):
            self.add_error('year', 'Choose a year to filter by publication date.')
        return data


class TagEditorForm(forms.ModelForm):
    appearance = forms.ChoiceField(choices=PALETTE, required=False, widget=forms.RadioSelect, label='Color')

    class Meta:
        model = Tag
        fields = ('title', 'description')
        labels = {'title': 'Name'}
        widgets = {'description': forms.Textarea(attrs={'rows': 5})}

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner
        choices = list(PALETTE)
        if self.instance.pk and self.instance.style not in dict(PALETTE):
            choices.append(('legacy', 'Keep existing setting'))
        self.fields['appearance'].choices = choices
        if not self.is_bound:
            self.initial['appearance'] = self.instance.style if self.instance.style in dict(PALETTE) else 'legacy'
        for name in ('title', 'description'):
            self.fields[name].widget.attrs['class'] = 'control'

    def clean_title(self):
        title = self.cleaned_data['title'].strip()
        if Tag.objects.filter(owner=self.owner, title__iexact=title).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('A tag with this name already exists.')
        return title

    def save(self, commit=True):
        tag = super().save(commit=False)
        tag.owner = self.owner
        appearance = self.cleaned_data['appearance']
        if appearance != 'legacy':
            tag.style = appearance
        if commit:
            tag.save()
        return tag


class TagQueryForm(forms.Form):
    term = forms.CharField(required=False, max_length=255, widget=forms.TextInput(attrs={'class': 'control', 'placeholder': 'Search tags by name or description…', 'aria-label': 'Search tags'}))
    sort = forms.ChoiceField(required=False, choices=(('name', 'Name A–Z'), ('count', 'Most bookmarks')), widget=forms.Select(attrs={'class': 'control', 'aria-label': 'Sort tags'}))
    page_size = forms.TypedChoiceField(required=False, coerce=int, empty_value=20, choices=((20, '20 per page'), (40, '40 per page'), (100, '100 per page')))
