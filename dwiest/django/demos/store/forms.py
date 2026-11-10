from django import forms

from .models import Catalog, Product, ProductVariant, ProductPhoto, StoreBranding, ShippingAddress, StoreOrder, StoreOrderItem


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
                  'footer_link_label', 'footer_link_url', 'copyright_text', 'coupon_code', 'coupon_percent']

    def clean_coupon_code(self):
        return self.cleaned_data['coupon_code'].strip().upper()

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


SHIPPING = {
    'ground': ('USPS Ground Advantage · estimated 2–5 business days', '6.95'),
    'priority': ('USPS Priority Mail · estimated 2–3 business days', '10.95'),
    'express': ('USPS Priority Mail Express · estimated 1–3 business days', '29.95'),
}


US_STATES = [('AL', 'Alabama'), ('AK', 'Alaska'), ('AZ', 'Arizona'), ('AR', 'Arkansas'), ('CA', 'California'), ('CO', 'Colorado'), ('CT', 'Connecticut'), ('DE', 'Delaware'), ('DC', 'District of Columbia'), ('FL', 'Florida'), ('GA', 'Georgia'), ('HI', 'Hawaii'), ('ID', 'Idaho'), ('IL', 'Illinois'), ('IN', 'Indiana'), ('IA', 'Iowa'), ('KS', 'Kansas'), ('KY', 'Kentucky'), ('LA', 'Louisiana'), ('ME', 'Maine'), ('MD', 'Maryland'), ('MA', 'Massachusetts'), ('MI', 'Michigan'), ('MN', 'Minnesota'), ('MS', 'Mississippi'), ('MO', 'Missouri'), ('MT', 'Montana'), ('NE', 'Nebraska'), ('NV', 'Nevada'), ('NH', 'New Hampshire'), ('NJ', 'New Jersey'), ('NM', 'New Mexico'), ('NY', 'New York'), ('NC', 'North Carolina'), ('ND', 'North Dakota'), ('OH', 'Ohio'), ('OK', 'Oklahoma'), ('OR', 'Oregon'), ('PA', 'Pennsylvania'), ('RI', 'Rhode Island'), ('SC', 'South Carolina'), ('SD', 'South Dakota'), ('TN', 'Tennessee'), ('TX', 'Texas'), ('UT', 'Utah'), ('VT', 'Vermont'), ('VA', 'Virginia'), ('WA', 'Washington'), ('WV', 'West Virginia'), ('WI', 'Wisconsin'), ('WY', 'Wyoming')]


class CheckoutForm(forms.ModelForm):
    state = forms.ChoiceField(choices=[('', 'Select a state')] + US_STATES)
    email = forms.EmailField()
    shipping_method = forms.ChoiceField(choices=[(key, '{} · ${}'.format(value[0], value[1])) for key, value in SHIPPING.items()])
    payment_method = forms.ChoiceField(choices=[('card_usd', 'Stripe · card in USD (simulation)'), ('usdc', 'Stripe · USDC stablecoin (simulation)')], widget=forms.RadioSelect)
    coupon = forms.CharField(max_length=40, required=False)
    acknowledge = forms.BooleanField(label='I understand this is a demo order and no money will be charged.')
    checkout_key = forms.UUIDField(widget=forms.HiddenInput)

    class Meta:
        model = ShippingAddress
        fields = ['name', 'email', 'line1', 'line2', 'city', 'state', 'postal_code', 'shipping_method', 'payment_method', 'coupon', 'acknowledge', 'checkout_key']

    def clean_state(self):
        value = self.cleaned_data['state'].upper()
        if value not in dict(US_STATES):
            raise forms.ValidationError('Enter a US state abbreviation or DC.')
        return value

    def clean_postal_code(self):
        import re
        value = self.cleaned_data['postal_code']
        if not re.fullmatch(r'\d{5}(-\d{4})?', value):
            raise forms.ValidationError('Enter a ZIP code such as 27601 or 27601-1234.')
        return value


class OrderUpdateForm(forms.Form):
    status = forms.ChoiceField(choices=StoreOrder.STATUS)
    tracking_number = forms.CharField(max_length=100, required=False)
    message = forms.CharField(widget=forms.Textarea, required=False, max_length=5000,
                              help_text='Sent to the customer with this update.')

    def clean(self):
        data = super().clean()
        if data.get('status') == 'fulfilled' and not data.get('tracking_number'):
            self.add_error('tracking_number', 'Enter a USPS tracking number to fulfill this order.')
        return data


OrderItemFormSet = forms.modelformset_factory(
    StoreOrderItem,
    fields=['quantity'], extra=0, can_delete=True)


class ShippingAddressForm(forms.ModelForm):
    state = forms.ChoiceField(choices=[('', 'Select a state')] + US_STATES)
    class Meta:
        model = ShippingAddress
        fields = ['name', 'line1', 'line2', 'city', 'state', 'postal_code']

    clean_state = CheckoutForm.clean_state
    clean_postal_code = CheckoutForm.clean_postal_code


class OrderEmailForm(forms.Form):
    email = forms.EmailField(label='Customer email', help_text='Order updates and notification retries use this address.')
