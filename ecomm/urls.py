from django.conf import settings
from django.conf.global_settings import MEDIA_URL
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from core.views import (CheckOut, ItemDetailView, ItemListView, OrderSummary,
                        PaymentView, add_one_item_to_cart, add_to_cart, home, AddCoupon,
                        products, remove_from_cart, remove_one_from_cart, RemoveCoupon, remove_coupon,
                        remove_whole_item_from_cart, RequestRefundView)
from ecomm.settings import STATIC_ROOT

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('', ItemListView.as_view(), name='home'),
    path('checkout/', CheckOut.as_view(), name='checkout'),
    path('products/', products, name='products'),
    path('request-refund/', RequestRefundView.as_view(), name='request-refund'),
    path('payment/<payment_option>', PaymentView.as_view(), name='payment'),
    path('add-coupon/', AddCoupon.as_view(), name='add-coupon'),
    path('remove-coupon/', remove_coupon, name='remove-coupon'),
    path('order-summary/', OrderSummary.as_view(), name='order-summary'),
    path('product/<slug>/', ItemDetailView.as_view(), name='product_detail'),
    path('add-to-cart/<slug>/', add_to_cart, name='add-to-cart'),
    path('add-one-to-cart/<slug>/', add_one_item_to_cart, name='add-one-to-cart'),
    path('remove-from-cart/<slug>/', remove_from_cart, name='remove-from-cart'),
    path('remove-one-from-cart/<slug>/',
         remove_one_from_cart, name='remove-one-from-cart'),
    path('remove-whole-item-from-cart/<slug>/',
         remove_whole_item_from_cart, name='remove-whole-item-from-cart'),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL,
                          document_root=settings.STATIC_ROOT)
