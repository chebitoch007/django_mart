from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import RedirectView

from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('store.urls', namespace='store')),

    # Unified user accounts system
    path('accounts/', include('users.urls')),

    # Other apps
    path('cart/', include('cart.urls', namespace='cart')),
    path('orders/', include('orders.urls', namespace='orders')),
    path('payment/', include('payment.urls', namespace='payment')),

    path('register/', RedirectView.as_view(pattern_name='users:register', permanent=True)),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)