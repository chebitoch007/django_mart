from django.urls import path
from core.views import session_keepalive

app_name = 'core'

urlpatterns = [
    path('session-keepalive/', session_keepalive, name='session_keepalive'),
]