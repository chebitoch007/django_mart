from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from .models import FAQ, TicketCategory, SupportTicket, TicketMessage, ContactMessage


def faq_list(request):
    """Display FAQs grouped by category"""
    category_slug = request.GET.get('category')
    search_query = request.GET.get('q', '')

    faqs = FAQ.objects.filter(is_published=True)

    if category_slug:
        faqs = faqs.filter(category__slug=category_slug)

    if search_query:
        faqs = faqs.filter(
            Q(question__icontains=search_query) |
            Q(answer__icontains=search_query)
        )

    categories = TicketCategory.objects.filter(is_active=True)

    # Group FAQs by category
    faq_by_category = {}
    for faq in faqs:
        if faq.category:
            if faq.category not in faq_by_category:
                faq_by_category[faq.category] = []
            faq_by_category[faq.category].append(faq)

    context = {
        'faq_by_category': faq_by_category,
        'categories': categories,
        'search_query': search_query,
        'selected_category': category_slug,
    }
    return render(request, 'support/faq_list.html', context)


def faq_helpful(request, faq_id):
    """Mark FAQ as helpful or not helpful"""
    if request.method == 'POST':
        faq = get_object_or_404(FAQ, id=faq_id)
        is_helpful = request.POST.get('helpful') == 'yes'

        if is_helpful:
            faq.helpful_count += 1
        else:
            faq.not_helpful_count += 1
        faq.save()

        return JsonResponse({'success': True})
    return JsonResponse({'success': False})


def contact(request):
    """Contact form"""
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone', '')
        subject = request.POST.get('subject')
        message_text = request.POST.get('message')

        contact_message = ContactMessage.objects.create(
            name=name,
            email=email,
            phone=phone,
            subject=subject,
            message=message_text,
            user=request.user if request.user.is_authenticated else None
        )

        messages.success(request, 'Your message has been sent successfully. We\'ll get back to you soon!')
        return redirect('support:contact')

    return render(request, 'support/contact.html')


@login_required
def ticket_list(request):
    """List user's support tickets"""
    tickets = SupportTicket.objects.filter(user=request.user).order_by('-created_at')

    status_filter = request.GET.get('status')
    if status_filter:
        tickets = tickets.filter(status=status_filter)

    context = {
        'tickets': tickets,
        'status_filter': status_filter,
    }
    return render(request, 'support/ticket_list.html', context)


@login_required
def ticket_create(request):
    """Create a new support ticket"""
    if request.method == 'POST':
        category_id = request.POST.get('category')
        subject = request.POST.get('subject')
        description = request.POST.get('description')
        priority = request.POST.get('priority', 'medium')

        try:
            category = get_object_or_404(TicketCategory, id=category_id)

            ticket = SupportTicket.objects.create(
                user=request.user,
                category=category,
                subject=subject,
                description=description,
                priority=priority
            )

            messages.success(request, f'Ticket {ticket.ticket_number} created successfully!')
            return redirect('support:ticket_detail', ticket_number=ticket.ticket_number)
        except Exception as e:
            messages.error(request, f'Error creating ticket: {str(e)}')

    categories = TicketCategory.objects.filter(is_active=True)
    context = {'categories': categories}
    return render(request, 'support/ticket_create.html', context)


@login_required
def ticket_detail(request, ticket_number):
    """View ticket details and messages"""
    ticket = get_object_or_404(SupportTicket, ticket_number=ticket_number, user=request.user)
    messages_list = ticket.messages.all().order_by('created_at')

    context = {
        'ticket': ticket,
        'messages': messages_list,
    }
    return render(request, 'support/ticket_detail.html', context)


@login_required
def ticket_reply(request, ticket_number):
    """Add a reply to a ticket"""
    if request.method == 'POST':
        ticket = get_object_or_404(SupportTicket, ticket_number=ticket_number, user=request.user)
        message_text = request.POST.get('message')

        if message_text:
            TicketMessage.objects.create(
                ticket=ticket,
                user=request.user,
                message=message_text,
                is_staff_reply=False
            )

            # Update ticket status if it was resolved
            if ticket.status == 'resolved':
                ticket.status = 'open'
                ticket.save()

            messages.success(request, 'Reply added successfully!')

        return redirect('support:ticket_detail', ticket_number=ticket_number)

    return redirect('support:ticket_list')