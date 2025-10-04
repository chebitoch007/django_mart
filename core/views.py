from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET


@require_GET
@csrf_exempt
def session_keepalive(request):
    """Reset session expiry time on any request"""
    if request.session:
        request.session.modified = True
        return HttpResponse(status=204)
    return HttpResponse(status=400)