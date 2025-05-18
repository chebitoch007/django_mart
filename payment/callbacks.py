from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse

@csrf_exempt
def mpesa_callback(request):
    # Process M-Pesa callback
    pass

@csrf_exempt
def airtel_callback(request):
    # Process Airtel callback
    pass