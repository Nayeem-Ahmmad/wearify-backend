from django.http import JsonResponse
from .models import SiteSettings


class MaintenanceModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/admin/'):
            return self.get_response(request)

        settings_obj = SiteSettings.load()
        if settings_obj.maintenance_mode:
            return JsonResponse(
                {
                    "maintenance": True,
                    "message": settings_obj.maintenance_message
                },
                status=503
            )

        return self.get_response(request)