from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from .models import (
    CompanyInfo, TeamMember, Career, JobApplication,
    Testimonial, Partner
)


def about(request):
    """Company about page"""
    company = CompanyInfo.load()
    team_members = TeamMember.objects.filter(is_active=True)[:8]
    testimonials = Testimonial.objects.filter(is_approved=True, is_featured=True)[:6]
    partners = Partner.objects.filter(is_active=True)

    context = {
        'company': company,
        'team_members': team_members,
        'testimonials': testimonials,
        'partners': partners,
    }
    return render(request, 'company/about.html', context)


def team_list(request):
    """Team members listing"""
    team_members = TeamMember.objects.filter(is_active=True)

    department = request.GET.get('department')
    if department:
        team_members = team_members.filter(position_category=department)

    context = {
        'team_members': team_members,
        'departments': TeamMember.POSITION_CHOICES,
        'selected_department': department,
    }
    return render(request, 'company/team_list.html', context)


def team_detail(request, slug):
    """Individual team member detail"""
    member = get_object_or_404(TeamMember, slug=slug, is_active=True)
    context = {'member': member}
    return render(request, 'company/team_detail.html', context)


def career_list(request):
    """List all job openings"""
    careers = Career.objects.filter(is_active=True)

    # Filters
    department = request.GET.get('department')
    employment_type = request.GET.get('type')
    experience = request.GET.get('experience')
    location = request.GET.get('location')

    if department:
        careers = careers.filter(department__icontains=department)
    if employment_type:
        careers = careers.filter(employment_type=employment_type)
    if experience:
        careers = careers.filter(experience_level=experience)
    if location:
        careers = careers.filter(location__icontains=location)

    # Get unique values for filters
    departments = Career.objects.filter(is_active=True).values_list('department', flat=True).distinct()
    locations = Career.objects.filter(is_active=True).values_list('location', flat=True).distinct()

    context = {
        'careers': careers,
        'departments': departments,
        'locations': locations,
        'employment_types': Career.EMPLOYMENT_TYPE_CHOICES,
        'experience_levels': Career.EXPERIENCE_CHOICES,
    }
    return render(request, 'company/career_list.html', context)


def career_detail(request, slug):
    """Job opening detail page"""
    career = get_object_or_404(Career, slug=slug, is_active=True)
    related_jobs = Career.objects.filter(
        department=career.department,
        is_active=True
    ).exclude(id=career.id)[:3]

    context = {
        'career': career,
        'related_jobs': related_jobs,
    }
    return render(request, 'company/career_detail.html', context)


def career_apply(request, slug):
    """Job application form"""
    career = get_object_or_404(Career, slug=slug, is_active=True)

    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        cover_letter = request.POST.get('cover_letter')
        linkedin_url = request.POST.get('linkedin_url', '')
        portfolio_url = request.POST.get('portfolio_url', '')
        resume = request.FILES.get('resume')

        if not resume:
            messages.error(request, 'Please upload your resume.')
            return redirect('company:career_apply', slug=slug)

        application = JobApplication.objects.create(
            career=career,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            resume=resume,
            cover_letter=cover_letter,
            linkedin_url=linkedin_url,
            portfolio_url=portfolio_url
        )

        messages.success(request,
                         'Your application has been submitted successfully! We\'ll review it and get back to you soon.')
        return redirect('company:career_detail', slug=slug)

    context = {'career': career}
    return render(request, 'company/career_apply.html', context)


def testimonial_list(request):
    """List all testimonials"""
    testimonials = Testimonial.objects.filter(is_approved=True)

    # Pagination
    paginator = Paginator(testimonials, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {'testimonials': page_obj}
    return render(request, 'company/testimonial_list.html', context)


def partner_list(request):
    """List all partners"""
    partners = Partner.objects.filter(is_active=True)
    context = {'partners': partners}
    return render(request, 'company/partner_list.html', context)