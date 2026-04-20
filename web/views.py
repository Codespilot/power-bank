
import secrets
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView
from api.models import User, UserRole
from api.auth import new_captcha_code

class HomePageView(TemplateView):
    template_name = "web/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_id = self.request.session.get("current_user_id")
        user = None
        is_admin = False
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                is_admin = UserRole.objects.filter(user=user, role=UserRole.ROLE_ADMIN).exists()
            except Exception:
                pass
        context["current_user"] = user
        context["user_is_admin"] = is_admin
        # Robust navbar highlighting
        path = self.request.path
        if path == "/":
            active_menu = "home"
        elif path.startswith("/user/"):
            active_menu = "user"
        elif path.startswith("/agent/"):
            active_menu = "agent"
        elif path.startswith("/order/"):
            active_menu = "order"
        elif path.startswith("/merchant/"):
            active_menu = "merchant"
        elif path.startswith("/profit/"):
            active_menu = "profit"
        elif path.startswith("/profile/"):
            active_menu = "profile"
        else:
            active_menu = ""
        context["active_menu"] = active_menu
        return context


class LoginPageView(TemplateView):
    template_name = "web/login.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        failed_count = int(self.request.session.get("login_failed_in_session", 0))
        need_captcha = failed_count >= 2

        source_token = secrets.token_urlsafe(16)
        self.request.session["login_source_token"] = source_token

        if need_captcha:
            self.request.session["login_captcha_code"] = new_captcha_code()
        else:
            self.request.session.pop("login_captcha_code", None)

        context.update(
            {
                "need_captcha": need_captcha,
                "captcha_code": "",
                "source_token": source_token,
                "current_user": None,
                "user_is_admin": False,
            }
        )
        return context


class CaptchaImageView(View):
    def get(self, request):
        code = new_captcha_code()
        request.session["login_captcha_code"] = code

        width, height = 120, 40
        noise_lines = []
        for _ in range(6):
            x1, y1 = secrets.randbelow(width), secrets.randbelow(height)
            x2, y2 = secrets.randbelow(width), secrets.randbelow(height)
            color = f"rgb({120 + secrets.randbelow(100)}, {120 + secrets.randbelow(100)}, {120 + secrets.randbelow(100)})"
            noise_lines.append(
                f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1" />'
            )

        text_nodes = []
        for index, char in enumerate(code):
            x = 16 + index * 24 + secrets.randbelow(5)
            y = 26 + secrets.randbelow(8)
            rotate = secrets.randbelow(21) - 10
            text_nodes.append(
                f'<text x="{x}" y="{y}" font-size="22" font-family="Arial" font-weight="bold" fill="#233f7a" transform="rotate({rotate} {x} {y})">{char}</text>'
            )

        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            '<rect width="100%" height="100%" rx="6" ry="6" fill="#edf3ff" />'
            + ''.join(noise_lines)
            + ''.join(text_nodes)
            + '</svg>'
        )

        response = HttpResponse(svg, content_type="image/svg+xml")
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response


class LogoutView(View):
    def get(self, request):
        request.session.flush()
        return redirect("/login")


class UserListPageView(TemplateView):
    template_name = "web/user_list.html"  # Now always in templates/web/
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 复用导航栏高亮逻辑
        context["active_menu"] = "user"
        user_id = self.request.session.get("current_user_id")
        user = None
        is_admin = False
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                is_admin = UserRole.objects.filter(user=user, role=UserRole.ROLE_ADMIN).exists()
            except Exception:
                pass
        context["current_user"] = user
        context["user_is_admin"] = is_admin
        return context

class MerchantListPageView(TemplateView):
    template_name = "web/merchant_list.html"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "merchant"
        user_id = self.request.session.get("current_user_id")
        user = None
        is_admin = False
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                is_admin = UserRole.objects.filter(user=user, role=UserRole.ROLE_ADMIN).exists()
            except Exception:
                pass
        context["current_user"] = user
        context["user_is_admin"] = is_admin
        return context

class MerchantHistoryPageView(TemplateView):
    template_name = "web/merchant_history_list.html"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "merchant"
        context["merchant_id"] = self.request.GET.get("merchant_id", "").strip()
        user_id = self.request.session.get("current_user_id")
        user = None
        is_admin = False
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                is_admin = UserRole.objects.filter(user=user, role=UserRole.ROLE_ADMIN).exists()
            except Exception:
                pass
        context["current_user"] = user
        context["user_is_admin"] = is_admin
        return context

class ProfitListPageView(TemplateView):
    template_name = "web/profit_list.html"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "profit"
        user_id = self.request.session.get("current_user_id")
        user = None
        is_admin = False
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                is_admin = UserRole.objects.filter(user=user, role=UserRole.ROLE_ADMIN).exists()
            except Exception:
                pass
        context["current_user"] = user
        context["user_is_admin"] = is_admin
        return context

class ProfilePageView(TemplateView):
    template_name = "web/profile.html"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "profile"
        user_id = self.request.session.get("current_user_id")
        user = None
        is_admin = False
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                is_admin = UserRole.objects.filter(user=user, role=UserRole.ROLE_ADMIN).exists()
            except Exception:
                pass
        context["current_user"] = user
        context["user_is_admin"] = is_admin
        return context

class OrderListPageView(TemplateView):
    template_name = "web/order_list.html"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "order"
        user_id = self.request.session.get("current_user_id")
        user = None
        is_admin = False
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                is_admin = UserRole.objects.filter(user=user, role=UserRole.ROLE_ADMIN).exists()
            except Exception:
                pass
        context["current_user"] = user
        context["user_is_admin"] = is_admin
        return context

class OrderImportListPageView(TemplateView):
    template_name = "web/order_import_list.html"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "order"
        user_id = self.request.session.get("current_user_id")
        user = None
        is_admin = False
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                is_admin = UserRole.objects.filter(user=user, role=UserRole.ROLE_ADMIN).exists()
            except Exception:
                pass
        context["current_user"] = user
        context["user_is_admin"] = is_admin
        return context