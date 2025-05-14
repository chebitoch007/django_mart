from django.shortcuts import render, redirect
from .forms import UserRegisterForm
from django.contrib import messages
from .forms import ProfileUpdateForm
from django.contrib.auth.decorators import login_required
from orders.models import Order


def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = UserRegisterForm()
    return render(request, 'users/register.html', {'form': form})


@login_required
def profile_update(request):
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated!')
            return redirect('users:profile')
    else:
        form = ProfileUpdateForm(instance=request.user)

    return render(request, 'users/profile_update.html', {
        'form': form
    })

def profile(request):
    try:
        orders = Order.objects.filter(user=request.user).order_by('-created')
        return render(request, 'users/profile.html', {
            'orders': orders
        })
    except Exception as e:
        # Handle the error appropriately
        return render(request, 'users/profile.html', {
            'error': str(e)
        })