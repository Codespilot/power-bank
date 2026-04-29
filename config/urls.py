from django.contrib import admin
from django.urls import include, path, re_path
from django.conf import settings
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from api.attachment.attachment_preview import attachment_preview_view
from api.term.term_preview import term_preview_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("swagger", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs"),
    path("swagger/", SpectacularSwaggerView.as_view(url_name="api-schema")),
    path("", include("web.urls")),
    path("api/", include("api.urls")),
    # 附件预览（含Token校验）
    re_path(r"^files/attachments/(?P<file_name>[^/]+)$", attachment_preview_view, name="file-preview"),
    # 协议文件预览（无需Token）
    re_path(r"^files/terms/(?P<file_name>[^/]+)$", term_preview_view, name="terms-file-preview"),
]
