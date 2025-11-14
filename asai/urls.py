# urls.py

from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import RedirectView

from django.conf import settings
from django.conf.urls.static import static

# Normalize ADMIN_URL from settings (strip leading/trailing slashes)
_admin_route = getattr(settings, 'ADMIN_URL', 'admin')
_admin_route = _admin_route.strip('/')  # ensure no leading/trailing slashes

urlpatterns = [
    path(f'{_admin_route}/', admin.site.urls),

    path('', include('store.urls', namespace='store')),
    # Unified user accounts system
    path('accounts/', include('users.urls', namespace='users')),
    path('account/', RedirectView.as_view(url='/accounts/', permanent=True)),
    # Other apps
    path('cart/', include('cart.urls', namespace='cart')),
    path('orders/', include('orders.urls', namespace='orders')),
    path('payment/', include('payment.urls', namespace='payment')),
    path('register/', RedirectView.as_view(pattern_name='users:register', permanent=True)),
    path('core/', include('core.urls')),

    # ===== NEW APPS =====
    path('support/', include('support.urls', namespace='support')),
    path('company/', include('company.urls', namespace='company')),
    path('blog/', include('blog.urls', namespace='blog')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
