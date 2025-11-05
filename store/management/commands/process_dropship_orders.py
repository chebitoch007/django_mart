# store/management/commands/process_dropship_orders.py

from django.core.management.base import BaseCommand
from django.utils import timezone

from store.aliexpress import generate_affiliate_link
from orders.models import Order


class Command(BaseCommand):
    help = 'Process recent dropshipping orders (last 24 hours)'

    def handle(self, *args, **options):
        # Get paid orders from last 24 hours
        orders = Order.objects.filter(
            status='PAID',
            created__gte=timezone.now() - timezone.timedelta(hours=24),
            items__product__is_dropship=True,
            items__dropship_processed=False
        ).distinct()

        if not orders.exists():
            self.stdout.write("No eligible dropshipping orders found.")
            return

        for order in orders:
            self.stdout.write(f"\nProcessing Order #{order.id} for {order.get_full_name()}")
            for item in order.items.filter(product__is_dropship=True, dropship_processed=False):
                self.process_item(item)

    def process_item(self, order_item):
        product = order_item.product
        order = order_item.order

        # Simulate affiliate order
        affiliate_link = generate_affiliate_link(product.supplier_url)
        print(f"  Ordering {order_item.quantity}x {product.name}")
        print(f"  Affiliate link: {affiliate_link}")
        print(f"  Ship to: {order.first_name} {order.last_name}, {order.address}, {order.city}")

        order_item.mark_as_processed(
            order_id="ALX123456",  # Simulated dropship order ID
            tracking="TRK987654321",  # Simulated tracking
            delivery="10-20 days"
        )

        self.stdout.write(self.style.SUCCESS(f"  ✓ Processed {product.name}"))
