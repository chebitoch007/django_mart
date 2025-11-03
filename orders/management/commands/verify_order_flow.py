# verify_order_flow.py
"""
Complete order flow verification script.
Run this to verify all backend fixes are working correctly.

Usage:
    python manage.py shell < orders/management/commands/verify_order_flow.py
"""

from orders.models import Order, OrderItem
from payment.models import Payment
from django.contrib.auth import get_user_model
from django.db.models import Count
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

print("=" * 60)
print("🔍 ORDER FLOW VERIFICATION SCRIPT")
print("=" * 60)

# Test 1: Check orders have payments
print("\n📋 Test 1: Checking Orders Have Payments...")
print("-" * 60)

orders = Order.objects.all()[:10]
orders_with_payment = 0
orders_without_payment = 0

for order in orders:
    try:
        payment = order.payment
        print(f"✅ Order #{order.id} has payment #{payment.id} - Status: {payment.status}")
        orders_with_payment += 1
    except Payment.DoesNotExist:
        print(f"❌ Order #{order.id} MISSING PAYMENT!")
        orders_without_payment += 1

        # Auto-fix: Create missing payment
        try:
            Payment.objects.create(
                order=order,
                amount=order.total,
                original_amount=order.total,
                converted_amount=order.total,
                phone_number=order.phone,
                status='PENDING',
            )
            print(f"   ✅ Auto-created payment for order #{order.id}")
        except Exception as e:
            print(f"   ❌ Failed to create payment: {e}")

print(f"\nSummary: {orders_with_payment} with payment, {orders_without_payment} without")

# Test 2: Verify Currency Field Access
print("\n💰 Test 2: Verifying Currency Field Access...")
print("-" * 60)

for order in Order.objects.all()[:5]:
    try:
        currency = order.total.currency
        amount = order.total.amount
        print(f"✅ Order #{order.id}: {currency} {amount}")
    except Exception as e:
        print(f"❌ Order #{order.id} currency access failed: {e}")

# Test 3: Check Phone Number Validation
print("\n📱 Test 3: Checking Phone Number Validation...")
print("-" * 60)

invalid_phones = 0
valid_phones = 0

for order in Order.objects.all()[:10]:
    if order.phone:
        if not order.phone.startswith('+'):
            print(f"⚠️  Order #{order.id} phone missing '+': {order.phone}")
            invalid_phones += 1
        else:
            print(f"✅ Order #{order.id} phone valid: {order.phone}")
            valid_phones += 1
    else:
        print(f"⚠️  Order #{order.id} has no phone number")

print(f"\nSummary: {valid_phones} valid, {invalid_phones} invalid")

# Test 4: Check New Shipping Fields
print("\n🚚 Test 4: Checking New Shipping Fields...")
print("-" * 60)

orders_with_instructions = 0
orders_with_billing_flag = 0

for order in Order.objects.all()[:10]:
    has_instructions = bool(order.delivery_instructions)
    if has_instructions:
        print(f"✅ Order #{order.id} has delivery instructions: {order.delivery_instructions[:50]}")
        orders_with_instructions += 1

    if order.billing_same_as_shipping:
        orders_with_billing_flag += 1

print(f"\nSummary: {orders_with_instructions} with instructions, {orders_with_billing_flag} with billing flag set")

# Test 5: Verify Order Items
print("\n📦 Test 5: Verifying Order Items...")
print("-" * 60)

orders_with_items = Order.objects.annotate(
    item_count=Count('items')
).filter(item_count__gt=0)[:5]

for order in orders_with_items:
    items = order.items.all()
    total_calc = sum(item.price.amount * item.quantity for item in items)
    stored_total = order.total.amount

    if abs(total_calc - stored_total) < 0.01:  # Allow for floating point errors
        print(f"✅ Order #{order.id}: {len(items)} items, total matches ({stored_total})")
    else:
        print(f"❌ Order #{order.id}: Total mismatch! Calculated: {total_calc}, Stored: {stored_total}")

# Test 6: Check Payment Status Distribution
print("\n📊 Test 6: Payment Status Distribution...")
print("-" * 60)

from django.db.models import Count

status_counts = Payment.objects.values('status').annotate(count=Count('status'))

for status in status_counts:
    print(f"   {status['status']}: {status['count']} payments")

# Test 7: Check Order Status Distribution
print("\n📊 Test 7: Order Status Distribution...")
print("-" * 60)

order_status_counts = Order.objects.values('status').annotate(count=Count('status'))

for status in order_status_counts:
    print(f"   {status['status']}: {status['count']} orders")

# Test 8: Verify Atomic Transaction Integrity
print("\n🔒 Test 8: Checking Order-Payment-Items Integrity...")
print("-" * 60)

integrity_issues = 0

for order in Order.objects.all()[:10]:
    issues = []

    # Check payment exists
    try:
        payment = order.payment
    except Payment.DoesNotExist:
        issues.append("Missing payment")

    # Check has items
    if not order.items.exists():
        issues.append("No items")

    # Check total matches items
    if order.items.exists():
        calc_total = sum(item.price.amount * item.quantity for item in order.items.all())
        if abs(calc_total - order.total.amount) > 0.01:
            issues.append(f"Total mismatch ({calc_total} vs {order.total.amount})")

    if issues:
        print(f"❌ Order #{order.id}: {', '.join(issues)}")
        integrity_issues += 1
    else:
        print(f"✅ Order #{order.id}: Complete and valid")

if integrity_issues == 0:
    print("\n🎉 All orders have complete integrity!")
else:
    print(f"\n⚠️  Found {integrity_issues} orders with integrity issues")

# Final Summary
print("\n" + "=" * 60)
print("✅ VERIFICATION COMPLETE")
print("=" * 60)
print("\n💡 Next Steps:")
print("   1. Fix any issues identified above")
print("   2. Run migrations: python manage.py migrate")
print("   3. Test order creation in browser")
print("   4. Test payment flow with M-Pesa/PayPal")
print("   5. Verify email notifications are sent")
print("\n" + "=" * 60)