# store/management/commands/process_dropship_orders.py
from django.core.management.base import BaseCommand

from store.aliexpress import generate_affiliate_link
from store.models import Product
from orders.models import Order, OrderItem
from django.conf import settings
import requests


class Command(BaseCommand):
    help = 'Processes dropshipping orders with AliExpress'

    def handle(self, *args, **options):
        # Get unprocessed dropship orders
        orders = Order.objects.filter(
            status='PAID',
            items__product__is_dropship=True
        ).distinct()

        for order in orders:
            for item in order.items.filter(product__is_dropship=True):
                self.process_item(item)

    def process_item(self, order_item):
        product = order_item.product
        affiliate_link = generate_affiliate_link(product.supplier_url)

        # This would be replaced with actual order API call
        print(f"Ordering {order_item.quantity} of {product.name}")
        print(f"Affiliate link: {affiliate_link}")
        print(f"Customer: {order_item.order.first_name} {order_item.order.last_name}")
        print(f"Address: {order_item.order.address}")

        # In production, you would:
        # 1. Call AliExpress API to place order
        # 2. Save tracking number
        # 3. Update order status

        # Mark as processed (for demo)
        order_item.dropship_processed = True
        order_item.save()