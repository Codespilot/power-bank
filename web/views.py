
import secrets
from django.conf import settings
from django.db.models import Exists, OuterRef
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView
from api.models import InviteCode, User, UserRole
from api.auth import new_captcha_code
import logging

logger = logging.getLogger(__name__)

class BaseTemplateView(TemplateView):
    """所有页面视图的基类，负责注入当前登录用户上下文和站点标题。

    使用 Exists 子查询将用户查询和管理员角色检查合并为一次数据库查询，
    避免每页两次查询。
    """

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_id = self.request.session.get("current_user_id")
        user = None
        is_admin = False
        if user_id:
            try:
                is_admin_subquery = UserRole.objects.filter(
                    user_id=OuterRef("id"), role=UserRole.ROLE_ADMIN
                )
                user = (
                    User.objects.annotate(_is_admin=Exists(is_admin_subquery))
                    .get(id=user_id)
                )
                is_admin = user._is_admin
            except Exception as e:
                logger.error("Error fetching user or admin status: %s", e)
        context["current_user"] = user
        context["user_is_admin"] = is_admin
        context["site_title"] = getattr(settings, "SITE_TITLE")
        return context

# 页面视图层：负责渲染后台模板并注入当前登录用户上下文。
class HomePageView(BaseTemplateView):
    """后台首页，同时负责导航高亮状态。"""
    template_name = "web/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
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
        elif path.startswith("/task/"):
            active_menu = "task"
        elif path.startswith("/profile/"):
            active_menu = "profile"
        elif path.startswith("/invite/"):
            active_menu = "invite"
        elif path.startswith("/wallet/"):
            active_menu = "wallet"
        elif path.startswith("/withdraw/"):
            active_menu = "withdraw"
        elif path.startswith("/term/"):
            active_menu = "term"
        elif path.startswith("/attachment/"):
            active_menu = "attachment"
        else:
            active_menu = ""
        context["active_menu"] = active_menu
        return context


class LoginPageView(TemplateView):
    """登录页，按失败次数决定是否显示图片验证码。"""

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
                "site_title": getattr(settings, "SITE_TITLE"),
            }
        )
        return context


class RegisterPageView(TemplateView):
    """注册页，只允许通过有效邀请码进入。"""

    template_name = "web/register.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invite_code = str(self.request.GET.get("invite_code") or "").strip().lower()
        invite_record = None
        invite_owner = None
        invite_error = ""

        if invite_code:
            if len(invite_code) == 8 and invite_code.isalnum() and invite_code == invite_code.lower():
                invite_record = InviteCode.objects.select_related("user").filter(code=invite_code, is_valid=True).first()
                if not invite_record:
                    invite_error = "邀请码无效，请确认后重试"
                else:
                    invite_owner = invite_record.user
            else:
                invite_error = "邀请码无效，请确认后重试"
        else:
            invite_error = "邀请码无效，请通过邀请链接注册"

        if invite_error:
            invite_code = ""

        display_name = ""
        if invite_owner:
            name = (invite_owner.fullname or "").strip() or invite_owner.username
            phone = (invite_owner.phone or "").strip()
            display_name = f"{name}（{phone}）" if phone else name

        context.update(
            {
                "invite_code": invite_code,
                "invite_owner_display": display_name,
                "invite_error": invite_error,
                "current_user": None,
                "user_is_admin": False,
                "site_title": getattr(settings, "SITE_TITLE"),
            }
        )
        return context


class CaptchaImageView(View):
    """动态生成登录验证码图片，避免明文验证码直接暴露在页面。"""

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
    """退出登录并清理当前会话。"""

    def get(self, request):
        request.session.flush()
        return redirect("/login")


# 以下页面主要承载后台管理界面，数据通过前端再请求对应 API 获取。
class UserListPageView(BaseTemplateView):
    """用户管理页面。"""

    template_name = "web/user_list.html"  # Now always in templates/web/
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 复用导航栏高亮逻辑
        context["active_menu"] = "user"
        return context


class AgentListPageView(BaseTemplateView):
    """代理商管理页面，仅展示当前用户的直属下级代理。"""

    template_name = "web/agent_list.html"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "agent"
        return context

class MerchantListPageView(BaseTemplateView):
    """商户管理页面。"""

    template_name = "web/merchant_list.html"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "merchant"
        return context

class MerchantHistoryPageView(BaseTemplateView):
    template_name = "web/merchant_history_list.html"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "merchant"
        context["merchant_id"] = self.request.GET.get("merchant_id", "").strip()
        return context

class ProfitListPageView(BaseTemplateView):
    """分润记录查询页面。"""

    template_name = "web/profit_list.html"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "profit"
        return context


class TaskRecordListPageView(BaseTemplateView):
    """分润任务运行记录页面。"""

    template_name = "web/task_record_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "task"
        return context

class ProfilePageView(BaseTemplateView):
    template_name = "web/profile.html"

class InvitePageView(BaseTemplateView):
    """邀请推广页面，展示并维护当前用户生成的邀请码。"""

    template_name = "web/invite.html"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "invite"
        return context

class WalletPageView(BaseTemplateView):
    """我的钱包页面，展示余额概况并支持提交提现申请。"""

    template_name = "web/wallet.html"

class WithdrawPageView(BaseTemplateView):
    """提现管理页面，管理员可审批，普通用户仅查看自己的申请。"""

    template_name = "web/withdraw_list.html"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "withdraw"
        return context

class OrderListPageView(BaseTemplateView):
    """订单列表页面。"""

    template_name = "web/order_list.html"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "order"
        return context

class OrderImportListPageView(BaseTemplateView):
    """订单导入记录页面。"""

    template_name = "web/order_import_list.html"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "order"
        return context


class TermListPageView(BaseTemplateView):
    """协议管理列表页面。"""

    template_name = "web/term_list.html"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "term"
        return context


class TermFormPageView(BaseTemplateView):
    """协议新增/编辑页面。"""

    template_name = "web/term_form.html"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "term"
        context["term_id"] = kwargs.get("id", "")
        return context


class AttachmentListPageView(BaseTemplateView):
    """附件管理列表页面。"""

    template_name = "web/attachment_list.html"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "attachment"
        return context
