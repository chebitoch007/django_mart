import json
import stripe
import requests
import base64
from datetime import datetime
from django.conf import settings
from django.views.generic import TemplateView
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from orders.models import Order
from .models import PaymentTransaction

stripe.api_key = settings.STRIPE_SECRET_KEY


class PaymentView(TemplateView):
    template_name = 'payment/payment.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = get_object_or_404(Order, id=self.kwargs['order_id'])

        context.update({
            'order': order,
            'stripe_key': settings.STRIPE_PUBLISHABLE_KEY,
            'paypal_client_id': settings.PAYPAL_CLIENT_ID,
            'mpesa_shortcode': settings.MPESA_SHORTCODE,
            'total_amount': order.get_total_cost()
        })
        return context


# Stripe Integration
@csrf_exempt
def stripe_webhook(request):

# Your existing Stripe webhook code
# ...

# PayPal Integration
def get_paypal_access_token():
    auth = (settings.PAYPAL_CLIENT_ID, settings.PAYPAL_SECRET)
    data = {'grant_type': 'client_credentials'}
    response = requests.post(
        f"https://api-m.{'sandbox' if settings.PAYPAL_ENVIRONMENT == 'sandbox' else ''}.paypal.com/v1/oauth2/token",
        auth=auth,
        data=data
    )
    return response.json().get('access_token')


@csrf_exempt
def create_paypal_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    access_token = get_paypal_access_token()

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {access_token}'
    }

    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "reference_id": str(order.id),
            "amount": {
                "currency_code": "USD",
                "value": str(order.get_total_cost())
            }
        }]
    }

    response = requests.post(
        f"https://api-m.{'sandbox' if settings.PAYPAL_ENVIRONMENT == 'sandbox' else ''}.paypal.com/v2/checkout/orders",
        json=payload,
        headers=headers
    )

    return JsonResponse(response.json())


@csrf_exempt
def capture_paypal_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    data = json.loads(request.body)
    paypal_order_id = data.get('orderID')

    access_token = get_paypal_access_token()
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {access_token}'
    }

    response = requests.post(
        f"https://api-m.{'sandbox' if settings.PAYPAL_ENVIRONMENT == 'sandbox' else ''}.paypal.com/v2/checkout/orders/{paypal_order_id}/capture",
        headers=headers
    )

    if response.status_code == 201:
        order.paid = True
        order.save()
        PaymentTransaction.objects.create(
            order=order,
            payment_method='PayPal',
            transaction_id=paypal_order_id,
            amount=order.get_total_cost(),
            status='completed'
        )
        return JsonResponse({'status': 'success'})

    return JsonResponse({'status': 'failed'}, status=400)


# M-Pesa Integration
def generate_mpesa_password():
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    data = f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}"
    return base64.b64encode(data.encode()).decode()


def get_mpesa_access_token():
    response = requests.get(
        'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials',
        auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET)
    )
    return response.json().get('access_token')


@csrf_exempt
def initiate_mpesa_payment(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    data = json.loads(request.body)

    access_token = get_mpesa_access_token()
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": generate_mpesa_password(),
        "Timestamp": datetime.now().strftime("%Y%m%d%H%M%S"),
        "TransactionType": "CustomerPayBillOnline",
        "Amount": str(order.get_total_cost()),
        "PartyA": data.get('phone_number'),
        "PartyB": settings.MPESA_SHORTCODE,
        "PhoneNumber": data.get('phone_number'),
        "CallBackURL": settings.MPESA_CALLBACK_URL,
        "AccountReference": f"ORDER_{order.id}",
        "TransactionDesc": f"Payment for order {order.id}"
    }

    response = requests.post(
        'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest',
        json=payload,
        headers=headers
    )

    if response.status_code == 200:
        return JsonResponse(response.json())

    return JsonResponse({'error': 'Payment initiation failed'}, status=400)


@csrf_exempt
def mpesa_callback(request):
    data = json.loads(request.body)
    result_code = data.get('Body', {}).get('stkCallback', {}).get('ResultCode')

    if result_code == 0:
        metadata = data['Body']['stkCallback']['CallbackMetadata']['Item']
        amount = next(item['Value'] for item in metadata if item['Name'] == 'Amount')
        mpesa_code = next(item['Value'] for item in metadata if item['Name'] == 'MpesaReceiptNumber')
        account_ref = data['Body']['stkCallback']['AccountReference']
        order_id = account_ref.split('_')[1]

        order = Order.objects.get(id=order_id)
        order.paid = True
        order.save()

        PaymentTransaction.objects.create(
            order=order,
            payment_method='M-Pesa',
            transaction_id=mpesa_code,
            amount=amount,
            status='completed'
        )

    return HttpResponse(status=200)