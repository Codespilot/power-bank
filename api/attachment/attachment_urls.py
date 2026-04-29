from django.urls import path

from .attachment_views import (
    AttachmentUploadFormView,
    AttachmentUploadBase64View,
    AttachmentListView,
    AttachmentDetailDeleteView,
    AttachmentTokenView,
)

attachment_urlpatterns = [
    # 上传
    path("attachments/upload/form", AttachmentUploadFormView.as_view(), name="api-attachments-upload-form"),
    path("attachments/upload/base64", AttachmentUploadBase64View.as_view(), name="api-attachments-upload-base64"),
    # 列表、详情、删除（不在Swagger展示）
    path("attachments", AttachmentListView.as_view(), name="api-attachments-list"),
    path("attachments/<int:id>", AttachmentDetailDeleteView.as_view(), name="api-attachments-detail"),
    # 生成文件访问Token
    path("attachments/token", AttachmentTokenView.as_view(), name="api-attachments-token"),
]
