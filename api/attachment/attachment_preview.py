import os
from io import BytesIO

from django.conf import settings
from django.http import FileResponse, HttpResponse, Http404

from api.models import Attachment
from api.auth import verify_file_access_token
from config.mime import get_mime_type

import logging

logger = logging.getLogger(__name__)

# 图片文件扩展名集合
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


def attachment_preview_view(request, file_name):
    """附件预览视图。

    处理 /files/attachments/{file_name}?token=xxx&thumb=100x100
    校验token后读取文件，支持图片裁剪。
    """
    token = request.GET.get("token", "")
    if not token:
        return HttpResponse("缺少token参数", status=403)

    # 查询附件记录
    attachment = Attachment.objects.filter(file_name=file_name).first()
    if not attachment:
        raise Http404("附件不存在")

    # 校验token
    if not verify_file_access_token(token, file_name, attachment.signature_key):
        return HttpResponse("token无效或已过期", status=403)

    # 读取文件
    file_path = os.path.join(settings.BASE_DIR, "files", "attachments", file_name)
    if not os.path.exists(file_path):
        raise Http404("文件不存在")

    file_ext = attachment.file_ext.lower()
    content_type = get_mime_type(file_ext)

    # 检查是否需要缩略图（仅图片文件）
    thumb_param = request.GET.get("thumb", "")
    if thumb_param and file_ext in IMAGE_EXTENSIONS:
        try:
            parts = thumb_param.split("x")
            if len(parts) == 2:
                thumb_width = int(parts[0])
                thumb_height = int(parts[1])
                if thumb_width > 0 and thumb_height > 0:
                    return _generate_thumbnail(file_path, thumb_width, thumb_height, content_type)
        except (ValueError, IndexError):
            pass

    # 直接返回文件
    response = FileResponse(open(file_path, "rb"), content_type=content_type)
    response["Cache-Control"] = "public, max-age=3600"
    return response


def _generate_thumbnail(file_path: str, width: int, height: int, content_type: str) -> HttpResponse:
    """生成缩略图，使用AspectFill模式裁剪。"""
    try:
        from PIL import Image
    except ImportError:
        logger.warning("Pillow未安装，返回原图")
        response = FileResponse(open(file_path, "rb"), content_type=content_type)
        response["Cache-Control"] = "public, max-age=3600"
        return response

    try:
        img = Image.open(file_path)
        # AspectFill 模式：先按比例缩放，再居中裁剪
        img_ratio = img.width / img.height
        target_ratio = width / height

        if img_ratio > target_ratio:
            # 图片更宽：按高度缩放，横向裁剪
            new_height = height
            new_width = int(height * img_ratio)
        else:
            # 图片更高：按宽度缩放，纵向裁剪
            new_width = width
            new_height = int(width / img_ratio)

        img = img.resize((new_width, new_height), Image.LANCZOS)

        # 居中裁剪
        left = (new_width - width) // 2
        top = (new_height - height) // 2
        img = img.crop((left, top, left + width, top + height))

        # 保存到内存
        buf = BytesIO()
        save_format = img.format or "JPEG"
        if save_format.upper() == "GIF":
            # 保留GIF动图时不裁剪
            img = Image.open(file_path)
            img.save(buf, format="GIF")
        else:
            img.save(buf, format=save_format)
        buf.seek(0)

        return HttpResponse(buf.getvalue(), content_type=content_type)
    except Exception as e:
        logger.error("生成缩略图失败: %s", e)
        response = FileResponse(open(file_path, "rb"), content_type=content_type)
        response["Cache-Control"] = "public, max-age=3600"
        return response
