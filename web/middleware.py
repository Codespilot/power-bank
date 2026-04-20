from django.shortcuts import redirect
from django.urls import reverse

EXCLUDE_PATHS = ["/login", "/register", "/api/auth/login/", "/api/auth/register/", "/api/token/grant", "/api/token/grant/", "/api/token/refresh", "/api/token/refresh/", "/static/"]

class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        auth_header = request.headers.get("Authorization", "")
        # 静态资源、登录页、API登录接口不拦截
        if any(path.startswith(p) for p in EXCLUDE_PATHS):
            return self.get_response(request)
        if path.startswith("/api/") and auth_header.lower().startswith("bearer "):
            return self.get_response(request)
        # 已登录
        if request.session.get("current_user_id"):
            return self.get_response(request)
        # 未登录，跳转到登录页并带next参数
        login_url = reverse("login")
        return redirect(f"{login_url}?next={path}")
