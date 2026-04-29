import base64
import os
import secrets
import uuid

from django.conf import settings
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from api.exceptions import CredentialError
from api.views import BaseAPIView
from api.models import Attachment, UserRole
from api.auth import (
    create_file_access_token,
    get_request_user_id,
)

from .attachment_serializers import (
    AttachmentUploadResponseSerializer,
    AttachmentBase64UploadSerializer,
)

from utils.generate_snowflake_id import generate_snowflake_id

import logging

logger = logging.getLogger(__name__)


def _check_admin(request) -> int:
    user_id = get_request_user_id(request)
    if not user_id:
        raise CredentialError("未登录")
    if not UserRole.objects.filter(user_id=user_id, role=UserRole.ROLE_ADMIN).exists():
        raise PermissionError("无权限，仅管理员可操作")
    return user_id


def _get_upload_dir() -> str:
    """获取附件存储目录，确保目录存在。"""
    upload_dir = settings.BASE_DIR / "files" / "attachments"
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def _save_uploaded_file(file_data: bytes, file_ext: str) -> str:
    """保存文件到磁盘，返回生成的UUID文件名。"""
    file_uuid = str(uuid.uuid4())
    file_name = f"{file_uuid}{file_ext}"
    upload_dir = _get_upload_dir()
    file_path = os.path.join(upload_dir, file_name)
    with open(file_path, "wb") as f:
        f.write(file_data)
    return file_name


def _create_attachment_record(
    file_name: str,
    origin_name: str,
    file_size: int,
    file_ext: str,
    upload_by_id: int,
) -> Attachment:
    """创建附件数据库记录。"""
    signature_key = secrets.token_hex(32)
    attachment = Attachment.objects.create(
        id=generate_snowflake_id(),
        file_name=file_name,
        origin_name=origin_name,
        file_size=file_size,
        file_ext=file_ext,
        signature_key=signature_key,
        upload_by_id=upload_by_id,
    )
    return attachment


def _serialize_attachment(attachment: Attachment) -> dict:
    return {
        "id": str(attachment.id),
        "file_name": attachment.file_name,
        "origin_name": attachment.origin_name,
        "file_size": attachment.file_size,
        "file_ext": attachment.file_ext,
        "upload_by_name": attachment.upload_by.fullname if attachment.upload_by else "",
        "created_at": BaseAPIView.format_datetime(attachment.created_at),
    }


class AttachmentUploadFormView(BaseAPIView):
    """表单方式上传附件。"""

    @extend_schema(
        tags=["attachments"],
        summary="上传附件（表单）",
        description="通过 multipart/form-data 上传文件。",
        responses={200: AttachmentUploadResponseSerializer, 400: dict},
    )
    def post(self, request):
        def _handle():
            user_id = get_request_user_id(request)
            if not user_id:
                raise CredentialError("未登录")

            file_obj = request.FILES.get("file")
            if not file_obj:
                return Response(
                    {"message": "请选择要上传的文件"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            origin_name = file_obj.name or "unknown"
            file_data = file_obj.read()
            file_size = len(file_data)
            _, file_ext = os.path.splitext(origin_name)
            if not file_ext:
                file_ext = ".bin"

            # 限制单个文件大小（100MB）
            max_size = 100 * 1024 * 1024
            if file_size > max_size:
                return Response(
                    {"message": f"文件大小不能超过100MB"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            file_name = _save_uploaded_file(file_data, file_ext)
            attachment = _create_attachment_record(
                file_name=file_name,
                origin_name=origin_name,
                file_size=file_size,
                file_ext=file_ext,
                upload_by_id=user_id,
            )

            return Response({
                "file_name": attachment.file_name,
                "file_size": attachment.file_size,
                "file_ext": attachment.file_ext,
            })

        return self.invoke(_handle)


class AttachmentUploadBase64View(BaseAPIView):
    """Base64方式上传附件。"""

    @extend_schema(
        tags=["attachments"],
        summary="上传附件（Base64）",
        description="通过JSON body中的base64内容上传文件。",
        request=AttachmentBase64UploadSerializer,
        responses={200: AttachmentUploadResponseSerializer, 400: dict},
    )
    def post(self, request):
        def _handle():
            user_id = get_request_user_id(request)
            if not user_id:
                raise CredentialError("未登录")

            serializer = AttachmentBase64UploadSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {"message": "参数错误", "errors": serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            origin_name = serializer.validated_data["name"]
            content_b64 = serializer.validated_data["content"]
            file_ext = serializer.validated_data.get("extension", "")

            if not file_ext:
                _, file_ext = os.path.splitext(origin_name)
                if not file_ext:
                    file_ext = ".bin"

            try:
                file_data = base64.b64decode(content_b64)
            except Exception:
                return Response(
                    {"message": "Base64解码失败"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            file_size = len(file_data)
            max_size = 100 * 1024 * 1024
            if file_size > max_size:
                return Response(
                    {"message": "文件大小不能超过100MB"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            file_name = _save_uploaded_file(file_data, file_ext)
            attachment = _create_attachment_record(
                file_name=file_name,
                origin_name=origin_name,
                file_size=file_size,
                file_ext=file_ext,
                upload_by_id=user_id,
            )

            return Response({
                "file_name": attachment.file_name,
                "file_size": attachment.file_size,
                "file_ext": attachment.file_ext,
            })

        return self.invoke(_handle)


class AttachmentListView(BaseAPIView):
    """附件列表查询接口（不在Swagger展示）。"""

    @extend_schema(exclude=True)
    def get(self, request):
        def _handle():
            _check_admin(request)

            keyword = str(request.GET.get("keyword", "")).strip()
            page = int(request.GET.get("page", 1))
            limit = int(request.GET.get("limit", 10))

            qs = Attachment.objects.select_related("upload_by").all()

            if keyword:
                qs = qs.filter(
                    Q(file_name__icontains=keyword) | Q(origin_name__icontains=keyword)
                )

            qs = qs.order_by("-created_at")

            total = qs.count()
            start = (page - 1) * limit
            end = start + limit
            items = qs[start:end]

            data = [_serialize_attachment(item) for item in items]
            return Response({
                "count": total,
                "page": page,
                "limit": limit,
                "results": data,
                "message": "查询成功",
            })

        return self.invoke(_handle)


class AttachmentDetailDeleteView(BaseAPIView):
    """附件详情查询与删除接口（不在Swagger展示，响应不包含signature_key）。

    处理 GET /api/attachments/{id} 和 DELETE /api/attachments/{id}
    """

    @extend_schema(exclude=True)
    def get(self, request, id):
        def _handle():
            _check_admin(request)

            attachment = Attachment.objects.select_related("upload_by").filter(id=id).first()
            if not attachment:
                return Response(
                    {"message": "附件不存在"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            data = _serialize_attachment(attachment)
            return Response({"data": data, "message": "查询成功"})

        return self.invoke(_handle)

    @extend_schema(exclude=True)
    def delete(self, request, id):
        def _handle():
            _check_admin(request)

            attachment = Attachment.objects.filter(id=id).first()
            if not attachment:
                return Response(
                    {"message": "附件不存在"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # 删除磁盘文件
            upload_dir = _get_upload_dir()
            file_path = os.path.join(upload_dir, attachment.file_name)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError as e:
                    logger.error("删除文件失败: %s", e)

            attachment.delete()
            return Response({"message": "删除成功"})

        return self.invoke(_handle)


class AttachmentTokenView(BaseAPIView):
    """获取附件访问Token（不在Swagger展示）。"""

    @extend_schema(exclude=True)
    def post(self, request):
        def _handle():
            user_id = get_request_user_id(request)
            if not user_id:
                raise CredentialError("未登录")

            file_name = str(request.data.get("file_name", "")).strip()
            if not file_name:
                return Response(
                    {"message": "file_name不能为空"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            attachment = Attachment.objects.filter(file_name=file_name).first()
            if not attachment:
                return Response(
                    {"message": "附件不存在"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            token = create_file_access_token(
                file_name=attachment.file_name,
                file_ext=attachment.file_ext,
                signature_key=attachment.signature_key,
            )
            return Response({
                "token": token,
                "expires_in": 7200,
                "file_name": attachment.file_name,
                "url": f"/files/attachments/{attachment.file_name}?token={token}",
            })

        return self.invoke(_handle)
