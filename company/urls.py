# ========== company/urls.py ==========
from django.urls import path
from . import views

app_name = 'company'

urlpatterns = [
    # About
    path('about/', views.about, name='about'),

    # Team
    path('team/', views.team_list, name='team'),
    path('team/<slug:slug>/', views.team_detail, name='team_detail'),

    # Careers
    path('careers/', views.career_list, name='careers'),
    path('careers/<slug:slug>/', views.career_detail, name='career_detail'),
    path('careers/<slug:slug>/apply/', views.career_apply, name='career_apply'),

    # Testimonials
    path('testimonials/', views.testimonial_list, name='testimonials'),

    # Partners
    path('partners/', views.partner_list, name='partners'),
]
