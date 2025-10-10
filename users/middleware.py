# users/middleware.py
import logging
from django.utils.timezone import now

logger = logging.getLogger(__name__)

class ViewDebugMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Determine if this is a class-based view
        view_name = (
            f"{view_func.view_class.__module__}.{view_func.view_class.__name__}"
            if hasattr(view_func, "view_class") else
            f"{view_func.__module__}.{view_func.__name__}"
        )

        user = request.user if request.user.is_authenticated else "Anonymous"
        query_params = dict(request.GET)
        post_data = {k: v for k, v in request.POST.items() if k.lower() not in ["password", "csrfmiddlewaretoken"]}

        client_ip = request.META.get('REMOTE_ADDR')

        log_message = (
            "\n====== VIEW DEBUG ======\n"
            f"Time: {now()}\n"
            f"View: {view_name}\n"
            f"Path: {request.path}\n"
            f"Method: {request.method}\n"
            f"User: {user}\n"
            f"Client IP: {client_ip}\n"
            f"Args: {view_args}\n"
            f"Kwargs: {view_kwargs}\n"
            f"Query Params: {query_params}\n"
            f"POST Data: {post_data}\n"
            "========================\n"
        )

        # Log to terminal & logger
        print(log_message)
        logger.debug(log_message)

        return None
