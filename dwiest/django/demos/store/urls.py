from django.urls import path

from . import views

app_name = 'store'
urlpatterns = [
    path('checkout/', views.checkout, name='checkout'),
    path('orders/<uuid:token>/', views.order_complete, name='order_complete'),
    path('manage/orders/', views.order_list, name='order_list'),
    path('manage/orders/<int:pk>/email/', views.order_email, name='order_email'),
    path('manage/orders/<int:pk>/', views.order_edit, name='order_edit'),
    path('manage/orders/<int:pk>/notifications/<int:event_pk>/retry/', views.retry_notification, name='retry_notification'),
    path('', views.home, name='home'),
    path('catalog/<slug:slug>/', views.home, name='catalog'),
    path('product/<slug:slug>/', views.product, name='product'),
    path('product/<slug:slug>/add/', views.add, name='add'),
    path('cart/', views.cart, name='cart'),
    path('cart/<int:pk>/', views.update, name='update'),
    path('manage/branding/', views.branding, name='branding'),
    path('manage/', views.manage, name='manage'),
    path('manage/products/new/', views.product_create, name='product_create'),
    path('manage/products/<int:pk>/', views.product_edit, name='product_edit'),
    path('manage/products/<int:pk>/photos/', views.upload_photos, name='photo_upload'),
    path('manage/products/<int:pk>/photos/<int:photo_pk>/', views.edit_photo, name='photo_edit'),
    path('manage/products/<int:pk>/photos/<int:photo_pk>/versions/<int:version>/restore/', views.restore_photo, name='photo_restore'),
    path('manage/products/<int:pk>/photos/<int:photo_pk>/delete/', views.delete_photo, name='photo_delete'),
    path('manage/catalogs/new/', views.catalog_create, name='catalog_create'),
    path('manage/catalogs/<int:pk>/', views.catalog_edit, name='catalog_edit'),
]
