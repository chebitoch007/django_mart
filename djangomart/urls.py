from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('store.urls')),  # Home and products
    path('accounts/', include('django.contrib.auth.urls')),  # Auth (login/logout)
    path('accounts/', include('users.urls')),  # Registration
    path('cart/', include('cart.urls')),  # Cart functionality
]