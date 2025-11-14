from django.urls import path
from . import views

app_name = 'support'

urlpatterns = [
    # FAQ
    path('faq/', views.faq_list, name='faq_list'),
    path('faq/<int:faq_id>/helpful/', views.faq_helpful, name='faq_helpful'),

    # Contact
    path('contact/', views.contact, name='contact'),

    # Support Tickets
    path('tickets/', views.ticket_list, name='ticket_list'),
    path('tickets/create/', views.ticket_create, name='ticket_create'),
    path('tickets/<str:ticket_number>/', views.ticket_detail, name='ticket_detail'),
    path('tickets/<str:ticket_number>/reply/', views.ticket_reply, name='ticket_reply'),
]