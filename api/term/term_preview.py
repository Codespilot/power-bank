import os

from django.conf import settings
from django.http import FileResponse, Http404

from config.mime import get_mime_type


def term_preview_view(request, file_name):
    """协议文件预览视图。

    直接读取 files/terms/ 下的文件，无需 Token 校验。
    """
    file_path = os.path.join(settings.BASE_DIR, "files", "terms", file_name)
    if not os.path.exists(file_path):
        raise Http404("文件不存在")

    ext = os.path.splitext(file_name)[1].lower()
    content_type = get_mime_type(ext)

    return FileResponse(open(file_path, "rb"), content_type=content_type)
