from decimal import Decimal
import re
from urllib.parse import urlparse

from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from django.db import transaction
from django.db.models import Q, OuterRef, Subquery
from django.utils import timezone
from ..models import AgentHistory, InviteCode, User, Wallet
from .user_serializers import (
    AgentAssignSerializer,
    IdMessageSerializer,
    LoginRequestSerializer,
    MessageSerializer,
    TokenGrantResponseSerializer,
    TokenGrantSerializer,
    TokenRefreshSerializer,
    UserCreateSerializer,
    UserDetailSerializer,
    UserListSerializer,
    UserPasswordChangeRequestSerializer,
    UserRegisterSerializer,
    UserResetPasswordSerializer,
)
from utils.generate_snowflake_id import generate_snowflake_id
from ..auth import (
    EMAIL_REGEX,
    MOBILE_REGEX,
    compute_lock_until,
    create_access_token,
    create_refresh_token,
    decode_jwt,
    get_request_user_id,
    get_user_by_identifier,
    hash_password,
    is_valid_username,
    verify_password,
)


def _authenticate_credentials(request, use_session_captcha: bool):
    """统一处理登录鉴权。

    session 登录与 token 授权都复用这套用户名、密码、锁定、验证码逻辑。
    """
    session = request.session
    payload = request.data if isinstance(request.data, dict) else {}

    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    captcha = str(payload.get("captcha", "")).strip()
    source_token = str(payload.get("source_token", "")).strip()

    print(
        f"Login attempt: username={username}, source_token={source_token}, captcha={captcha}, session_token={session.get('login_source_token', '')}"
    )

    if not is_valid_username(username):
        return None, Response(
            {"message": "用户名格式必须是中国大陆手机号或邮箱"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    referer = request.headers.get("Referer", "")
    referer_path = urlparse(referer).path
    session_source_token = str(session.get("login_source_token", ""))
    # if use_session_captcha and (not referer_path.startswith("/login") or not session_source_token or source_token != session_source_token):
    #     return None, Response({"message": "非法请求来源"}, status=status.HTTP_403_FORBIDDEN)

    need_captcha = (
        use_session_captcha and int(session.get("login_failed_in_session", 0)) >= 2
    )
    if need_captcha:
        session_captcha = str(session.get("login_captcha_code", ""))
        if not session_captcha or captcha != session_captcha:
            return None, Response(
                {"message": "验证码错误"}, status=status.HTTP_400_BAD_REQUEST
            )

    user = get_user_by_identifier(username)
    if user is None:
        if use_session_captcha:
            session["login_failed_in_session"] = (
                int(session.get("login_failed_in_session", 0)) + 1
            )
        return None, Response(
            {"message": "用户名或密码错误"}, status=status.HTTP_400_BAD_REQUEST
        )

    now = timezone.now()
    if user.locked_out and user.locked_out > now:
        return None, Response(
            {
                "message": f"账号已锁定，请在 {user.locked_out.strftime('%Y-%m-%d %H:%M:%S')} 后重试"
            },
            status=status.HTTP_423_LOCKED,
        )

    if not verify_password(user, password):
        user.access_failed_count += 1
        lock_until = compute_lock_until(user.access_failed_count)
        user.locked_out = lock_until
        user.save(update_fields=["access_failed_count", "locked_out"])

        if use_session_captcha:
            session["login_failed_in_session"] = (
                int(session.get("login_failed_in_session", 0)) + 1
            )

        if lock_until:
            return None, Response(
                {"message": f"账号已锁定至 {lock_until.strftime('%Y-%m-%d %H:%M:%S')}"},
                status=status.HTTP_423_LOCKED,
            )
        return None, Response(
            {"message": "用户名或密码错误"}, status=status.HTTP_400_BAD_REQUEST
        )

    user.access_failed_count = 0
    user.locked_out = None
    user.save(update_fields=["access_failed_count", "locked_out"])

    if use_session_captcha:
        session["login_failed_in_session"] = 0
        session.pop("login_captcha_code", None)

    return user, None


class LoginAPIView(APIView):
    """用户登录"""

    permission_classes = [AllowAny]
    serializer_class = LoginRequestSerializer

    @extend_schema(
        tags=["users"],
        summary="用户登录",
        request=LoginRequestSerializer,
        responses={
            200: IdMessageSerializer,
            400: MessageSerializer,
            423: MessageSerializer,
        },
    )
    def post(self, request):
        user, error_response = _authenticate_credentials(
            request, use_session_captcha=True
        )
        if error_response is not None:
            return error_response

        request.session["current_user_id"] = user.id
        next_url = request.GET.get("next") or request.data.get("next") or "/"
        return Response({"message": "登录成功", "user_id": user.id, "next": next_url})


class TokenGrantView(APIView):
    permission_classes = [AllowAny]
    serializer_class = TokenGrantSerializer

    @extend_schema(
        tags=["token"],
        summary="获取访问令牌",
        request=TokenGrantSerializer,
        responses={
            200: TokenGrantResponseSerializer,
            400: MessageSerializer,
            423: MessageSerializer,
        },
    )
    def post(self, request):
        user, error_response = _authenticate_credentials(
            request, use_session_captcha=False
        )
        if error_response is not None:
            return error_response

        access_token, expires_in = create_access_token(user)
        refresh_token, refresh_expires_in = create_refresh_token(user)
        return Response(
            {
                "message": "获取token成功",
                "token_type": "Bearer",
                "access_token": access_token,
                "expires_in": expires_in,
                "refresh_token": refresh_token,
                "refresh_expires_in": refresh_expires_in,
                "user_id": user.id,
            }
        )


class TokenRefreshView(APIView):
    """刷新Token"""

    permission_classes = [AllowAny]
    serializer_class = TokenRefreshSerializer

    @extend_schema(
        tags=["token"],
        summary="刷新访问令牌",
        request=TokenRefreshSerializer,
        responses={
            200: TokenGrantResponseSerializer,
            400: MessageSerializer,
            404: MessageSerializer,
        },
    )
    def post(self, request):
        refresh_token = str(request.data.get("refresh_token", "")).strip()
        if not refresh_token:
            return Response(
                {"message": "refresh_token不能为空"}, status=status.HTTP_400_BAD_REQUEST
            )

        payload = decode_jwt(refresh_token, expected_type="refresh")
        user = User.objects.filter(id=payload.get("user_id")).first()
        if not user:
            return Response({"message": "用户不存在"}, status=status.HTTP_404_NOT_FOUND)

        access_token, expires_in = create_access_token(user)
        new_refresh_token, refresh_expires_in = create_refresh_token(user)
        return Response(
            {
                "message": "刷新token成功",
                "token_type": "Bearer",
                "access_token": access_token,
                "expires_in": expires_in,
                "refresh_token": new_refresh_token,
                "refresh_expires_in": refresh_expires_in,
                "user_id": user.id,
            }
        )


def _resolve_superior_user(agent_phone: str = "", invite_code: str = ""):
    """解析用户的上级代理。

    优先通过邀请码反查 InviteCode 记录；后台手工创建用户时仍兼容手机号方式。
    """
    invite_code = str(invite_code or "").strip().lower()
    agent_phone = str(agent_phone or "").strip()

    if invite_code:
        if not re.fullmatch(r"[a-z0-9]{8}", invite_code):
            raise ValueError("邀请码无效")
        invite_record = (
            InviteCode.objects.select_related("user")
            .filter(code=invite_code, is_valid=True)
            .first()
        )
        if not invite_record or not invite_record.user:
            raise ValueError("邀请码无效")
        return invite_record.user, invite_record

    if agent_phone:
        superior_user = User.objects.filter(phone=agent_phone).first()
        if not superior_user:
            raise ValueError(f"无法找到对应的用户{agent_phone}")
        return superior_user, None

    return None, None


def _create_user_account(data, *, invite_code: str = ""):
    """创建用户及其钱包，并在需要时绑定上级代理或邀请码。"""
    raw_username = str(data.get("username", ""))
    username = "".join(raw_username.split()).lower()
    fullname = str(data.get("fullname", "")).strip()
    phone = str(data.get("phone", "")).strip()
    email = str(data.get("email", "")).strip()
    password = str(data.get("password", "")).strip()
    agent_phone = str(
        data.get("agent_phone")
        or data.get("agent_mobile")
        or data.get("superior_phone")
        or ""
    ).strip()
    agent_rate_raw = str(data.get("agent_rate", "")).strip()

    if not re.match(r"^[a-z0-9_]{4,32}$", username):
        raise ValueError("用户名格式错误，仅支持4-32位小写字母、数字和下划线")
    if User.objects.filter(username=username).exists():
        raise ValueError("用户名已存在")
    if not fullname:
        raise ValueError("姓名不能为空")
    if not MOBILE_REGEX.fullmatch(phone):
        raise ValueError("手机号格式错误")
    if User.objects.filter(phone=phone).exists():
        raise ValueError("手机号已存在")
    if email:
        if not EMAIL_REGEX.fullmatch(email):
            raise ValueError("邮箱格式错误")
        if User.objects.filter(email=email).exists():
            raise ValueError("邮箱已存在")
    if not password or len(password) < 6:
        raise ValueError("密码至少6位")

    superior_user, invite_record = _resolve_superior_user(
        agent_phone=agent_phone, invite_code=invite_code
    )
    agent_rate = Decimal("0.00")
    if invite_record:
        agent_rate = Decimal(str(invite_record.rate or "0.00"))
    elif superior_user and agent_rate_raw:
        agent_rate = _parse_agent_rate(agent_rate_raw)

    from api.auth import hash_password

    password_hash, password_salt = hash_password(password)

    with transaction.atomic():
        locked_invite_record = None
        if invite_record:
            locked_invite_record = (
                InviteCode.objects.select_for_update()
                .select_related("user")
                .filter(id=invite_record.id)
                .first()
            )
            if (
                not locked_invite_record
                or not locked_invite_record.is_valid
                or not locked_invite_record.user_id
            ):
                raise ValueError("邀请码无效")
            superior_user = locked_invite_record.user
            agent_rate = Decimal(str(locked_invite_record.rate or "0.00"))

        user = User.objects.create(
            id=generate_snowflake_id(),
            username=username,
            fullname=fullname,
            phone=phone,
            email=email or None,
            invite_code=locked_invite_record.code if locked_invite_record else None,
            password_hash=password_hash,
            password_salt=password_salt,
            agent=superior_user,
            agent_rate=agent_rate if superior_user else Decimal("0.00"),
            created_at=timezone.now(),
        )
        Wallet.objects.create(id=user.id)

        if locked_invite_record:
            locked_invite_record.register_count = (
                int(locked_invite_record.register_count or 0) + 1
            )
            locked_invite_record.save(update_fields=["register_count"])
    return user


class UserListPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "limit"
    page_query_param = "page"
    max_page_size = 200

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.page.paginator.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
                "message": "查询成功",
            }
        )


# @extend_schema_view(
#     get=extend_schema(
#         tags=["users"],
#         summary="获取用户列表",
#         parameters=[
#             OpenApiParameter(name="keyword", description="用户名、手机号或邮箱关键字", required=False, type=str),
#             OpenApiParameter(name="id", description="按用户ID筛选", required=False, type=str),
#             OpenApiParameter(name="exclude_id", description="排除指定用户ID", required=False, type=str),
#             OpenApiParameter(name="direct_subordinates", description="是否只查询直属下级，传 1 或 true 生效", required=False, type=str),
#             OpenApiParameter(name="page", description="页码", required=False, type=int),
#             OpenApiParameter(name="limit", description="每页数量", required=False, type=int),
#         ],
#     )
# )
@extend_schema(exclude=True)  # 该接口不在自动文档中展示
class UserListView(generics.ListAPIView):
    serializer_class = UserListSerializer
    pagination_class = UserListPagination

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        try:
            page = self.paginate_queryset(queryset)
        except NotFound:
            return Response(
                {
                    "count": queryset.count(),
                    "next": None,
                    "previous": None,
                    "results": [],
                    "message": "查询成功",
                },
                status=status.HTTP_200_OK,
            )

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def get_queryset(self):
        qs = User.objects.select_related("agent").all().order_by("-created_at")
        # 使用 Subquery 批量获取钱包余额，消除 N+1 查询
        wallet_subquery = Wallet.objects.filter(id=OuterRef("id")).values(
            "total_amount"
        )[:1]
        qs = qs.annotate(wallet_total_amount=Subquery(wallet_subquery))
        keyword = self.request.GET.get("keyword", "").strip()
        user_id = self.request.GET.get("id", "").strip()
        exclude_user_id = self.request.GET.get("exclude_id", "").strip()
        direct_subordinates = (
            str(self.request.GET.get("direct_subordinates", "")).strip().lower()
        )

        # 代理商管理页会传入 direct_subordinates=1，此时只看当前登录用户的直属下级。
        if direct_subordinates in {"1", "true", "yes"}:
            current_user_id = get_request_user_id(self.request)
            if not current_user_id:
                return User.objects.none()
            qs = qs.filter(agent_id=current_user_id)

        if user_id:
            try:
                qs = qs.filter(id=int(user_id))
            except (TypeError, ValueError):
                return User.objects.none()

        if exclude_user_id:
            try:
                qs = qs.exclude(id=int(exclude_user_id))
            except (TypeError, ValueError):
                return User.objects.none()

        if keyword:
            qs = qs.filter(
                Q(username__icontains=keyword)
                | Q(phone__icontains=keyword)
                | Q(email__icontains=keyword)
            )
        return qs


def _parse_agent_rate(value) -> Decimal:
    """解析并验证分润比例（接口仅接受 0~1 的值）。"""
    raw = str(value or "").strip()
    if not raw:
        return Decimal("0.00")
    rate = Decimal(raw)
    if rate < 0:
        raise ValueError("分润比例不能小于0")
    if rate > Decimal("1.00"):
        raise ValueError("分润比例不能超过1")
    return rate


def _is_descendant_user(superior_id: int, subordinate_id: int) -> bool:
    """Check whether superior_id is in subordinate_id's descendant tree."""
    visited = set()
    pending = [subordinate_id]

    while pending:
        current_id = pending.pop()
        if current_id in visited:
            continue
        visited.add(current_id)

        child_ids = list(
            User.objects.filter(agent_id=current_id).values_list("id", flat=True)
        )
        if superior_id in child_ids:
            return True
        pending.extend(child_ids)

    return False


# @extend_schema_view(
#     post=extend_schema(
#         tags=["users"],
#         summary="创建用户",
#         request=UserCreateSerializer,
#         responses={201: IdMessageSerializer, 400: MessageSerializer},
#     )
# )
@extend_schema(exclude=True)  # 该接口不在自动文档中展示
class UserCreateView(generics.CreateAPIView):
    serializer_class = UserCreateSerializer

    def create(self, request, *args, **kwargs):
        try:
            user = _create_user_account(request.data)
        except Exception as exc:
            return Response(
                {"message": str(exc) or "创建失败"}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(
            {"message": "创建成功", "id": str(user.id)}, status=status.HTTP_201_CREATED
        )


class RegisterAPIView(APIView):
    """用户注册"""

    permission_classes = [AllowAny]
    serializer_class = UserRegisterSerializer

    @extend_schema(
        tags=["users"],
        summary="用户注册",
        request=UserRegisterSerializer,
        responses={200: IdMessageSerializer, 400: MessageSerializer},
    )
    def post(self, request):
        captcha = str(request.data.get("captcha", "")).strip()
        session_captcha = str(request.session.get("login_captcha_code", "")).strip()
        if not session_captcha or captcha != session_captcha:
            return Response(
                {"message": "验证码错误"}, status=status.HTTP_400_BAD_REQUEST
            )

        password = str(request.data.get("password", "")).strip()
        confirm_password = str(request.data.get("confirm_password", "")).strip()
        if password != confirm_password:
            return Response(
                {"message": "两次输入的密码不一致"}, status=status.HTTP_400_BAD_REQUEST
            )

        invite_code = (
            str(
                request.data.get("invite_code")
                or request.query_params.get("invite_code")
                or ""
            )
            .strip()
            .lower()
        )
        if not invite_code:
            return Response(
                {"message": "邀请码无效，请通过邀请链接注册"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = _create_user_account(request.data, invite_code=invite_code)
        except Exception as exc:
            return Response(
                {"message": str(exc) or "注册失败"}, status=status.HTTP_400_BAD_REQUEST
            )

        request.session.pop("login_captcha_code", None)
        return Response({"message": "注册成功", "id": str(user.id)})


@extend_schema_view(get=extend_schema(
        tags=["users"],
        summary="获取用户详情",
        responses={
            200: UserDetailSerializer,
            401: MessageSerializer,
            404: MessageSerializer,
        },
    )
)
class UserDetailView(generics.RetrieveAPIView):
    queryset = (
        User.objects.select_related("agent")
        .annotate(
            wallet_total_amount=Subquery(
                Wallet.objects.filter(id=OuterRef("id")).values("total_amount")[:1]
            )
        )
        .all()
    )
    serializer_class = UserDetailSerializer
    lookup_field = "id"


class UserAgentAssignView(APIView):
    serializer_class = AgentAssignSerializer

    # @extend_schema(
    #     tags=["users"],
    #     summary="分配上级代理商",
    #     request=AgentAssignSerializer,
    #     responses={200: MessageSerializer, 400: MessageSerializer, 404: MessageSerializer},
    # )
    @extend_schema(exclude=True)  # 该接口不在自动文档中展示
    def post(self, request, id=None):
        superior_phone = (
            request.data.get("superior_phone") or request.data.get("agent_phone") or ""
        ).strip()
        superior_id_raw = request.data.get("superior_id")
        subordinate_id = request.data.get("subordinate_id") or id
        rate_raw = request.data.get("rate", request.data.get("agent_rate", "0"))

        try:
            subordinate_id = int(str(subordinate_id).strip())
            rate = _parse_agent_rate(rate_raw)
        except (TypeError, ValueError, AttributeError) as exc:
            return Response(
                {"message": str(exc) or "参数错误"}, status=status.HTTP_400_BAD_REQUEST
            )

        superior = None
        if superior_phone:
            superior = User.objects.filter(phone=superior_phone).first()
            if not superior:
                return Response(
                    {"message": f"无法找到对应的用户{superior_phone}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            superior_id = int(superior.id)
        else:
            try:
                superior_id = int(str(superior_id_raw).strip())
            except (TypeError, ValueError, AttributeError):
                return Response(
                    {"message": "参数错误"}, status=status.HTTP_400_BAD_REQUEST
                )

        if id is not None and subordinate_id != id:
            return Response(
                {"message": "参数不匹配"}, status=status.HTTP_400_BAD_REQUEST
            )

        if superior_id == subordinate_id:
            return Response(
                {"message": "不能将自己设置为上级代理商"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if superior is None:
            superior = User.objects.filter(id=superior_id).first()
        subordinate = User.objects.filter(id=subordinate_id).first()
        if not superior or not subordinate:
            return Response({"message": "用户不存在"}, status=status.HTTP_404_NOT_FOUND)

        if _is_descendant_user(superior_id, subordinate_id):
            return Response(
                {"message": "所选上级代理商不能是当前用户的下级代理商"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            subordinate = (
                User.objects.select_for_update().filter(id=subordinate_id).first()
            )
            old_superior_id = subordinate.agent_id

            subordinate.agent = superior
            subordinate.agent_rate = rate
            subordinate.save(update_fields=["agent", "agent_rate"])

            AgentHistory.objects.create(
                id=generate_snowflake_id(),
                old_superior_id=old_superior_id,
                new_superior_id=superior_id,
                created_at=timezone.now(),
            )

        return Response({"message": "上级代理商分配成功"})


class UserPasswordResetView(APIView):
    serializer_class = UserResetPasswordSerializer

    # @extend_schema(
    #     tags=["users"],
    #     summary="重置用户密码",
    #     request=UserResetPasswordSerializer,
    #     responses={200: MessageSerializer, 400: MessageSerializer, 404: MessageSerializer},
    # )
    @extend_schema(exclude=True)  # 该接口不在自动文档中展示
    def post(self, request, id):
        user = User.objects.filter(id=id).first()
        if not user:
            return Response({"message": "用户不存在"}, status=status.HTTP_404_NOT_FOUND)
        password = request.data.get("password", "").strip()
        if not password or len(password) < 6:
            return Response(
                {"message": "密码至少6位"}, status=status.HTTP_400_BAD_REQUEST
            )
        password_hash, password_salt = hash_password(password)
        user.password_hash = password_hash
        user.password_salt = password_salt
        user.save(update_fields=["password_hash", "password_salt"])
        return Response({"message": "密码重置成功"})


class UserPasswordChangeView(APIView):
    @extend_schema(
        tags=["users"],
        summary="修改用户密码",
        request=UserPasswordChangeRequestSerializer,
        responses={
            200: MessageSerializer,
            400: MessageSerializer,
            401: MessageSerializer,
        },
    )
    def post(self, request):
        user_id = get_request_user_id(request)
        if not user_id:
            return Response({"message": "未登录"}, status=status.HTTP_401_UNAUTHORIZED)

        user = User.objects.filter(id=user_id).first()
        if not user:
            return Response({"message": "用户不存在"}, status=status.HTTP_404_NOT_FOUND)

        old_password = str(request.data.get("old_password", ""))
        new_password = str(request.data.get("new_password", ""))
        confirm_password = str(request.data.get("confirm_password", ""))

        if not verify_password(user, old_password):
            return Response(
                {"message": "原密码错误"}, status=status.HTTP_400_BAD_REQUEST
            )

        if not new_password or len(new_password) < 6:
            return Response(
                {"message": "新密码至少6位"}, status=status.HTTP_400_BAD_REQUEST
            )

        if new_password != confirm_password:
            return Response(
                {"message": "两次输入的新密码不一致"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        password_hash_value, password_salt_value = hash_password(new_password)
        user.password_hash = password_hash_value
        user.password_salt = password_salt_value
        user.save(update_fields=["password_hash", "password_salt"])
        return Response({"message": "密码修改成功"})
