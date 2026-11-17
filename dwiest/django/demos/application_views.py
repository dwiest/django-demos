from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .application_access import navigation


@login_required
def desktop_toys(request):
    catalog = navigation(request)
    sections = [group for group in catalog['groups'] if group['key'] == 'toys']
    return render(request, 'dwiest-django-demos/applications/toys.html',
                  {'toy_sections': sections[0]['sections'] if sections else [],
                   'toy_count': len(catalog['toys'])})
