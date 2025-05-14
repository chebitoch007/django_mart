from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('store.urls', namespace='store')),
    path('cart/', include('cart.urls', namespace='cart')),  # Add this line
    path('accounts/', include('django.contrib.auth.urls')),  # For auth views
    path('users/', include('users.urls', namespace='users')),
    # If you have a users app
]


