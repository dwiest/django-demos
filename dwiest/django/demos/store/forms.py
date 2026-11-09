from django import forms

from .models import Catalog, Product, ProductVariant, ProductPhoto, StoreBranding


class QuantityForm(forms.Form):
    quantity = forms.IntegerField(min_value=1, max_value=99, initial=1)


class AddToCartForm(QuantityForm):
    variant = forms.ModelChoiceField(queryset=ProductVariant.objects.none(), empty_label=None)

    def __init__(self, *args, **kwargs):
        product = kwargs.pop('product')
        super().__init__(*args, **kwargs)
        self.fields['variant'].queryset = product.variants.filter(active=True)


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'slug', 'description', 'image_url', 'image_alt', 'published', 'catalogs']

    def clean_image_url(self):
        value = self.cleaned_data['image_url']
        if value and not value.startswith('https://'):
            raise forms.ValidationError('Use an HTTPS image URL.')
        return value


class CatalogForm(forms.ModelForm):
    class Meta:
        model = Catalog
        fields = ['name', 'slug', 'description', 'published']


VariantFormSet = forms.inlineformset_factory(
    Product, ProductVariant, fields=['name', 'sku', 'price', 'active'],
    extra=1, can_delete=True, min_num=1, validate_min=True,
)


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

    def value_from_datadict(self, data, files, name):
        return files.getlist(name)


class MultipleImageField(forms.FileField):
    def clean(self, data, initial=None):
        from .media import MAX_BATCH, prepare_image
        if not data:
            raise forms.ValidationError('Select at least one photo.')
        if len(data) > MAX_BATCH:
            raise forms.ValidationError('Upload at most 10 photos at once.')
        return [prepare_image(super(MultipleImageField, self).clean(value, initial)) for value in data]


class PhotoUploadForm(forms.Form):
    photos = MultipleImageField(widget=MultipleFileInput(attrs={
        'multiple': True, 'accept': 'image/jpeg,image/png,image/webp'}),
        help_text='JPEG, PNG, or WebP. Up to 10 photos per upload, 10 MB and 24 megapixels each.')


class PhotoDetailsForm(forms.ModelForm):
    class Meta:
        model = ProductPhoto
        fields = ['alt_text', 'sort_order']


class StoreBrandingForm(forms.ModelForm):
    header_image = forms.FileField(required=False, help_text='Optional logo or header artwork. JPEG, PNG, or WebP; up to 10 MB.')
    remove_header_image = forms.BooleanField(required=False, label='Remove current header image')
    footer_image = forms.FileField(required=False, help_text='Optional footer artwork. JPEG, PNG, or WebP; up to 10 MB.')
    remove_footer_image = forms.BooleanField(required=False, label='Remove current footer image')

    class Meta:
        model = StoreBranding
        fields = ['name', 'tagline', 'introduction', 'header_image_alt',
                  'footer_heading', 'footer_text', 'footer_image_alt', 'contact_email',
                  'footer_link_label', 'footer_link_url', 'copyright_text']

    def clean_footer_link_url(self):
        value = self.cleaned_data['footer_link_url']
        if value and not value.startswith('https://'):
            raise forms.ValidationError('Use an HTTPS link.')
        return value

    def clean(self):
        from .media import prepare_image
        cleaned = super().clean()
        if bool(cleaned.get('footer_link_label')) != bool(cleaned.get('footer_link_url')):
            raise forms.ValidationError('Provide both a footer link label and URL, or leave both blank.')
        for location in ('header', 'footer'):
            field = location + '_image'
            upload = cleaned.get(field)
            if upload:
                if cleaned.get('remove_' + field):
                    self.add_error(field, 'Choose either a new image or removal.')
                else:
                    try:
                        cleaned[field] = prepare_image(upload)
                    except forms.ValidationError as error:
                        self.add_error(field, error)
        return cleaned
