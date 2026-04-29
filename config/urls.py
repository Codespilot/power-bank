from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve
from django.conf import settings
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("swagger", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs"),
    path("swagger/", SpectacularSwaggerView.as_view(url_name="api-schema")),
    path("", include("web.urls")),
    path("api/", include("api.urls")),
    # 协议发布的HTML文件访问
    re_path(r"^files/(?P<path>.*)$", serve, {
        "document_root": settings.BASE_DIR / "files",
    }),
]
