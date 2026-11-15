from django.http import HttpResponse
from django.urls import include, path
from .urls import urlpatterns as bookmark_patterns


def placeholder(request):
    return HttpResponse('Test navigation target')


demos_patterns = [path('', placeholder, name='home'),
                  path('bookmarks/', include((bookmark_patterns, 'bookmarks'), namespace='bookmarks'))]
for name in ['invoicer', 'journal', 'qrcode', 'otp', 'expenses', 'inventory', 'file', 'news', 'selenium', 'store']:
    demos_patterns.append(path(name + '/', include(([path('', placeholder, name='home'), path('index/', placeholder, name='index')], name), namespace=name)))
urlpatterns = [path('', include((demos_patterns, 'demos'), namespace='demos'))]
