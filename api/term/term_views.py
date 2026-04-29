import os
import uuid
from datetime import datetime

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from api.exceptions import CredentialError
from api.serializers import GenericResponseSerializer
from ..views import BaseAPIView
from ..models import Term, UserRole

from .term_serializers import (
    TermListRequestSerializer,
    TermListResponseSerializer,
    TermDetailResponseSerializer,
    TermCreateRequestSerializer,
    TermUpdateRequestSerializer,
    TermPublicResponseSerializer,
)

from utils.generate_snowflake_id import generate_snowflake_id

import logging

logger = logging.getLogger(__name__)


def _check_admin(request) -> int:
    """检查当前用户是否为管理员，返回用户ID。"""
    from api.auth import get_request_user_id
    user_id = get_request_user_id(request)
    if not user_id:
        raise CredentialError("未登录")
    if not UserRole.objects.filter(user_id=user_id, role=UserRole.ROLE_ADMIN).exists():
        raise PermissionError("无权限，仅管理员可操作")
    return user_id


def _get_term_status_name(status: int) -> str:
    return dict(Term.STATUS_CHOICES).get(status, "")


def _get_term_type_name(t: int) -> str:
    return dict(Term.TYPE_CHOICES).get(t, "")


def _get_platform_name(platform: int) -> str:
    return dict(Term.PLATFORM_CHOICES).get(platform, "")


def _serialize_term(term: Term) -> dict:
    return {
        "id": str(term.id),
        "name": term.name,
        "type": term.type,
        "type_name": _get_term_type_name(term.type),
        "platform": term.platform,
        "platform_name": _get_platform_name(term.platform) if term.platform else "",
        "file_name": term.file_name,
        "status": term.status,
        "status_name": _get_term_status_name(term.status),
        "content": term.content,
        "created_at": BaseAPIView.format_datetime(term.created_at),
        "updated_at": BaseAPIView.format_datetime(term.updated_at),
        "published_at": BaseAPIView.format_datetime(term.published_at) if term.published_at else None,
        "is_valid": term.is_valid,
    }


def _serialize_term_list(term: Term) -> dict:
    return {
        "id": str(term.id),
        "name": term.name,
        "type": term.type,
        "type_name": _get_term_type_name(term.type),
        "platform": term.platform,
        "platform_name": _get_platform_name(term.platform) if term.platform else "",
        "file_name": term.file_name,
        "status": term.status,
        "status_name": _get_term_status_name(term.status),
        "created_at": BaseAPIView.format_datetime(term.created_at),
        "published_at": BaseAPIView.format_datetime(term.published_at) if term.published_at else None,
        "is_valid": term.is_valid,
    }


class TermListView(BaseAPIView):
    """协议列表查询与新增接口。"""

    @extend_schema(
        tags=["terms"],
        summary="获取协议列表",
        description="分页查询协议列表，支持关键字搜索和类型、平台筛选。",
        parameters=[
            OpenApiParameter(name="keyword", description="关键字，搜索名称", required=False, type=str),
            OpenApiParameter(name="type", description="协议类型：1-隐私政策、2-用户协议", required=False, type=int),
            OpenApiParameter(name="platform", description="平台：1-全部、2-Web、3-小程序、4-App、5-其他", required=False, type=int),
            OpenApiParameter(name="page", description="页码，默认1", required=False, type=int),
            OpenApiParameter(name="limit", description="每页数量，默认10", required=False, type=int),
        ],
        responses={200: GenericResponseSerializer[TermListResponseSerializer]},
    )
    def get(self, request):
        def _handle():
            _check_admin(request)

            keyword = str(request.GET.get("keyword", "")).strip()
            t = request.GET.get("type")
            platform = request.GET.get("platform")
            page = int(request.GET.get("page", 1))
            limit = int(request.GET.get("limit", 10))

            qs = Term.objects.filter(id__isnull=False)

            if keyword:
                qs = qs.filter(name__icontains=keyword)
            if t:
                try:
                    qs = qs.filter(type=int(t))
                except (TypeError, ValueError):
                    pass
            if platform:
                try:
                    qs = qs.filter(platform=int(platform))
                except (TypeError, ValueError):
                    pass

            qs = qs.order_by("-created_at")

            total = qs.count()

            # 手动分页
            start = (page - 1) * limit
            end = start + limit
            items = qs[start:end]

            data = [_serialize_term_list(item) for item in items]
            return Response({
                "count": total,
                "page": page,
                "limit": limit,
                "results": data,
                "message": "查询成功",
            })

        return self.invoke(_handle)

    @extend_schema(
        tags=["terms"],
        exclude=True,  # 暂时不在自动文档中展示此接口
        summary="新增协议",
        description="新增一条协议记录。同一类型同一平台只允许一条记录。",
        request=TermCreateRequestSerializer,
        responses={200: dict, 400: dict},
    )
    def post(self, request):
        def _handle():
            _check_admin(request)

            name = str(request.data.get("name", "")).strip()
            t = request.data.get("type")
            platform = request.data.get("platform")
            content = str(request.data.get("content", "")).strip()

            if not name:
                raise ValueError("协议名称不能为空")
            if len(name) > 50:
                raise ValueError("协议名称长度不能超过50个字")
            if not t:
                raise ValueError("协议类型不能为空")
            if not platform:
                raise ValueError("平台不能为空")
            if not content:
                raise ValueError("协议内容不能为空")

            try:
                t = int(t)
                platform = int(platform)
            except (TypeError, ValueError):
                raise ValueError("参数格式错误")

            if t not in dict(Term.TYPE_CHOICES):
                raise ValueError("无效的协议类型")
            if platform not in dict(Term.PLATFORM_CHOICES):
                raise ValueError("无效的平台")

            # 同一类型同一平台只允许一条有效记录
            if Term.objects.filter(type=t, platform=platform, is_valid=True).exists():
                raise ValueError(f"同一类型同一平台已存在有效记录")

            term = Term.objects.create(
                id=generate_snowflake_id(),
                type=t,
                name=name,
                platform=platform,
                content=content,
                status=Term.STATUS_DRAFT,
            )

            return Response({
                "id": str(term.id),
                "message": "新增成功",
            })

        return self.invoke(_handle)


class TermDetailView(BaseAPIView):
    """协议详情、编辑、删除接口。"""

    @extend_schema(
        tags=["terms"],
        exclude=True,  # 暂时不在自动文档中展示此接口
        summary="获取协议详情",
        description="查询指定协议的详细信息。",
        responses={200: TermDetailResponseSerializer, 404: dict},
    )
    def get(self, request, id):
        def _handle():
            _check_admin(request)

            try:
                term = Term.objects.get(id=id, is_valid=True)
            except Term.DoesNotExist:
                return Response({"message": "协议不存在"}, status=status.HTTP_404_NOT_FOUND)

            return Response({**_serialize_term(term), "message": "查询成功"})

        return self.invoke(_handle)

    @extend_schema(
        tags=["terms"],
        exclude=True,  # 暂时不在自动文档中展示此接口
        summary="编辑协议",
        description="修改指定协议的内容。修改后发布状态改为待发布。",
        request=TermUpdateRequestSerializer,
        responses={200: dict, 400: dict, 404: dict},
    )
    def post(self, request, id):
        def _handle():
            _check_admin(request)

            try:
                term = Term.objects.get(id=id, is_valid=True)
            except Term.DoesNotExist:
                return Response({"message": "协议不存在"}, status=status.HTTP_404_NOT_FOUND)

            name = str(request.data.get("name", "")).strip()
            t = request.data.get("type")
            platform = request.data.get("platform")
            content = str(request.data.get("content", "")).strip()

            if not name:
                raise ValueError("协议名称不能为空")
            if len(name) > 50:
                raise ValueError("协议名称长度不能超过50个字")
            if not t:
                raise ValueError("协议类型不能为空")
            if not platform:
                raise ValueError("平台不能为空")
            if not content:
                raise ValueError("协议内容不能为空")

            try:
                t = int(t)
                platform = int(platform)
            except (TypeError, ValueError):
                raise ValueError("参数格式错误")

            if t not in dict(Term.TYPE_CHOICES):
                raise ValueError("无效的协议类型")
            if platform not in dict(Term.PLATFORM_CHOICES):
                raise ValueError("无效的平台")

            # 同一类型同一平台只允许一条有效记录（排除自身）
            if Term.objects.filter(type=t, platform=platform, is_valid=True).exclude(id=id).exists():
                raise ValueError(f"同一类型同一平台已存在有效记录")

            term.name = name
            term.type = t
            term.platform = platform
            term.content = content
            term.status = Term.STATUS_DRAFT
            term.save()

            return Response({"message": "修改成功"})

        return self.invoke(_handle)

    @extend_schema(
        tags=["terms"],
        exclude=True,  # 暂时不在自动文档中展示此接口
        summary="删除协议",
        description="删除指定协议（软删除）。",
        responses={200: dict, 404: dict},
    )
    def delete(self, request, id):
        def _handle():
            _check_admin(request)

            try:
                term = Term.objects.get(id=id, is_valid=True)
            except Term.DoesNotExist:
                return Response({"message": "协议不存在"}, status=status.HTTP_404_NOT_FOUND)

            term.is_valid = False
            term.save()
            return Response({"message": "删除成功"})

        return self.invoke(_handle)


class TermEnableDisableView(BaseAPIView):
    """协议启用/禁用接口。"""

    @extend_schema(
        tags=["terms"],
        summary="启用协议",
        description="启用指定协议（设置is_valid=True）。",
        responses={200: dict, 404: dict},
    )
    def put(self, request, id, action):
        def _handle():
            _check_admin(request)

            try:
                term = Term.objects.get(id=id)
            except Term.DoesNotExist:
                return Response({"message": "协议不存在"}, status=status.HTTP_404_NOT_FOUND)

            if action == "enable":
                term.is_valid = True
                msg = "启用成功"
            elif action == "disable":
                term.is_valid = False
                msg = "禁用成功"
            else:
                return Response({"message": "无效操作"}, status=status.HTTP_400_BAD_REQUEST)

            term.save()
            return Response({"message": msg})

        return self.invoke(_handle)


class TermPublishView(BaseAPIView):
    """协议发布接口。"""

    @extend_schema(
        tags=["terms"],
        summary="发布协议",
        description="发布协议，生成HTML文件保存到files/terms/目录。",
        responses={200: dict, 400: dict, 404: dict},
    )
    def put(self, request, id):
        def _handle():
            _check_admin(request)

            try:
                term = Term.objects.get(id=id, is_valid=True)
            except Term.DoesNotExist:
                return Response({"message": "协议不存在"}, status=status.HTTP_404_NOT_FOUND)

            if term.status == Term.STATUS_PUBLISHED:
                raise ValueError("该协议已发布，请勿重复发布")

            # 生成HTML文件
            file_uuid = str(uuid.uuid4())
            file_name = f"{file_uuid}.html"

            files_dir = settings.BASE_DIR / "files" / "terms"
            files_dir.mkdir(parents=True, exist_ok=True)

            file_path = files_dir / file_name
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(term.content)

            term.file_name = file_name
            term.status = Term.STATUS_PUBLISHED
            term.published_at = timezone.now()
            term.save()

            return Response({
                "message": "发布成功",
                "file_name": file_name,
            })

        return self.invoke(_handle)


class TermPrivacyView(BaseAPIView):
    """获取隐私政策（公开接口）。"""

    @extend_schema(
        tags=["terms"],
        summary="获取隐私政策",
        description="公开接口，根据平台代码查询隐私政策内容，返回html格式内容。platform为空或0时默认为1。",
        parameters=[
            OpenApiParameter(name="platform", description="平台代码，为空或0时默认为1", required=False, type=int),
        ],
        responses={200: TermPublicResponseSerializer, 404: dict},
    )
    def get(self, request):
        platform = request.GET.get("platform", "0")
        try:
            platform = int(platform)
        except (TypeError, ValueError):
            platform = 0
        if platform == 0:
            platform = 1

        term = Term.objects.filter(
            type=Term.TYPE_PRIVACY,
            platform=platform,
            is_valid=True,
            status=Term.STATUS_PUBLISHED,
        ).first()

        if not term or not term.file_name:
            return Response(
                {"message": "隐私政策未找到"},
                status=status.HTTP_404_NOT_FOUND,
            )

        content = self._read_file_content(term.file_name)
        if content is None:
            return Response(
                {"message": "隐私政策文件不存在"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({
            "name": term.name,
            "content": content,
            "publish_time": BaseAPIView.format_datetime(term.published_at) if term.published_at else "",
        })

    def _read_file_content(self, file_name: str) -> str | None:
        file_path = settings.BASE_DIR / "files" / "terms" / file_name
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return None


class TermUserAgreementView(BaseAPIView):
    """获取用户协议（公开接口）。"""

    @extend_schema(
        tags=["terms"],
        summary="获取用户协议",
        description="公开接口，根据平台代码查询用户协议内容，返回html格式内容。platform为空或0时默认为1。",
        parameters=[
            OpenApiParameter(name="platform", description="平台代码，为空或0时默认为1", required=False, type=int),
        ],
        responses={200: TermPublicResponseSerializer, 404: dict},
    )
    def get(self, request):
        platform = request.GET.get("platform", "0")
        try:
            platform = int(platform)
        except (TypeError, ValueError):
            platform = 0
        if platform == 0:
            platform = 1

        term = Term.objects.filter(
            type=Term.TYPE_USER_AGREEMENT,
            platform=platform,
            is_valid=True,
            status=Term.STATUS_PUBLISHED,
        ).first()

        if not term or not term.file_name:
            return Response(
                {"message": "用户协议未找到"},
                status=status.HTTP_404_NOT_FOUND,
            )

        content = self._read_file_content(term.file_name)
        if content is None:
            return Response(
                {"message": "用户协议文件不存在"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({
            "name": term.name,
            "content": content,
            "publish_time": BaseAPIView.format_datetime(term.published_at) if term.published_at else "",
        })

    def _read_file_content(self, file_name: str) -> str | None:
        file_path = settings.BASE_DIR / "files" / "terms" / file_name
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return None
