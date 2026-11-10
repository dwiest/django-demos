"""Private customer pages using the site's existing Django identity."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .forms import CustomerAddressForm, CustomerEmailForm, CustomerProfileForm
from .models import CustomerAddress, StoreOrder
from .views import page


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def account(request):
    profile = CustomerProfileForm(initial={'first_name': request.user.first_name,
                                          'last_name': request.user.last_name})
    email = CustomerEmailForm(user=request.user)
    notice = ''
    if request.method == 'POST':
        if request.POST.get('action') == 'profile':
            profile = CustomerProfileForm(request.POST)
            if profile.is_valid():
                for field, value in profile.cleaned_data.items():
                    setattr(request.user, field, value)
                request.user.save(update_fields=['first_name', 'last_name'])
                return redirect('demos:store:account')
        elif request.POST.get('action') == 'email':
            email = CustomerEmailForm(request.POST, user=request.user)
            if email.is_valid():
                token = signing.dumps({'user': request.user.pk, 'old': request.user.email,
                                       'new': email.cleaned_data['email'],
                                       'password': request.user.get_session_auth_hash()}, salt='store-email-change')
                link = request.build_absolute_uri(reverse('demos:store:confirm_email', args=[token]))
                try:
                    count = send_mail('Confirm your email change',
                                      'Confirm your new email address: ' + link,
                                      settings.DEFAULT_FROM_EMAIL, [email.cleaned_data['email']])
                    if count != 1:
                        raise RuntimeError('Email was not sent')
                    notice = 'Check your new email address for a confirmation link. It expires in one hour.'
                except Exception:
                    email.add_error(None, 'We could not send the confirmation. Please try again later.')
    return page(request, 'account.html', profile_form=profile, email_form=email,
                addresses=CustomerAddress.objects.filter(user=request.user), notice=notice)


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def confirm_email(request, token):
    valid = False
    try:
        data = signing.loads(token, salt='store-email-change', max_age=3600)
        valid = (data['user'] == request.user.pk and data['old'] == request.user.email
                 and data['password'] == request.user.get_session_auth_hash())
    except (signing.BadSignature, KeyError):
        pass
    if valid and request.method == 'POST':
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
            if (user.email == data['old'] and user.get_session_auth_hash() == data['password'] and
                    not get_user_model().objects.filter(Q(email__iexact=data['new']) | Q(username__iexact=data['new'])).exclude(pk=user.pk).exists()):
                # The existing authentication uses the email as username.
                if user.username.lower() == user.email.lower():
                    user.username = data['new']
                user.email = data['new']
                user.save(update_fields=['email', 'username'])
                return redirect('demos:store:account')
            valid = False
    response = page(request, 'confirm_email.html', valid=valid)
    response['Referrer-Policy'] = 'no-referrer'
    return response


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def address(request, pk=None):
    entry = get_object_or_404(CustomerAddress, pk=pk, user=request.user) if pk else CustomerAddress(user=request.user)
    if request.method == 'POST' and request.POST.get('action') == 'delete' and pk:
        entry.delete()
        return redirect('demos:store:account')
    form = CustomerAddressForm(request.POST if request.method == 'POST' else None, instance=entry)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('demos:store:account')
    return page(request, 'customer_address.html', form=form, entry=entry)


@never_cache
@login_required
def orders(request):
    from django.core.paginator import Paginator
    result = StoreOrder.objects.filter(user=request.user)
    return page(request, 'customer_orders.html', orders=Paginator(result, 20).get_page(request.GET.get('page')))


@never_cache
@login_required
def order(request, pk):
    result = get_object_or_404(StoreOrder.objects.select_related('shipping_address').prefetch_related('items'),
                               pk=pk, user=request.user)
    return page(request, 'guest_order.html', order=result)
