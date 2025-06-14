# payments/api.py
from rest_framework.decorators import api_view
from rest_framework.response import Response

from payment.models import Payment


@api_view(['GET'])
def payment_status(request, transaction_id):
    try:
        payment = Payment.objects.get(
            transaction_id=transaction_id,
            user=request.user
        )
        return Response({
            'status': payment.status,
            'amount': payment.amount,
            'provider': payment.get_provider_display()
        })
    except Payment.DoesNotExist:
        return Response({'error': 'Transaction not found'}, status=404)
