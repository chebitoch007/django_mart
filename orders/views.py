from django.http import Http404
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, render, redirect
from django.db.models import Prefetch
from .models import Order, OrderItem
from cart.models import Cart
from django.contrib.auth.decorators import login_required


class OrderListView(LoginRequiredMixin, ListView):
    model = Order
    template_name = 'orders/order_list.html'
    context_object_name = 'orders'
    paginate_by = 10

    def get_queryset(self):
        return Order.objects.filter(
            user=self.request.user
        ).select_related('user').prefetch_related(
            Prefetch('items', queryset=OrderItem.objects.select_related('product'))
        ).only(
            'id', 'created', 'status', 'currency', 'user__email'
        ).order_by('-created')


class OrderDetailView(LoginRequiredMixin, DetailView):
    model = Order
    template_name = 'orders/order_detail.html'
    context_object_name = 'order'

    ORDER_FIELDS = [
        'id', 'created', 'status', 'currency', 'payment_method',
        'address', 'postal_code', 'city'
    ]
    USER_FIELDS = ['user__first_name', 'user__last_name', 'user__email']
    ITEM_FIELDS = [
        'items__price', 'items__quantity',
        'items__product__id', 'items__product__name',
        'items__product__price'
    ]

    def _build_order_queryset(self):
        """Build optimized queryset for order details."""
        items_queryset = OrderItem.objects.select_related('product')

        return (Order.objects
        .select_related('user')
        .prefetch_related(
            Prefetch('items', queryset=items_queryset)
        )
        .only(
            *self.ORDER_FIELDS,
            *self.USER_FIELDS,
            *self.ITEM_FIELDS
        )
        .filter(
            pk=self.kwargs['pk'],
            user=self.request.user
        ))

def get_object(self):
    try:
        return get_object_or_404(
            self._build_order_queryset(),
            pk=self.kwargs.get('pk')
        )
    except (ValueError, KeyError):
        raise Http404("Invalid order ID")


def checkout(request):
    # Get the user's cart
    try:
        cart = Cart.objects.get(user=request.user)
    except Cart.DoesNotExist:
        return redirect("cart:cart_detail")

    # Add payment processing logic here
    context = {
        'cart': cart,
    }
    return render(request, "orders/checkout.html", context)


@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).order_by('-created')
    return render(request, 'orders/history.html', {'orders': orders})

