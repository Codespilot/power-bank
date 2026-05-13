from rest_framework import serializers


class AttachmentUploadResponseSerializer(serializers.Serializer):
    file_name = serializers.CharField(help_text="存储文件名（UUID）")
    file_size = serializers.IntegerField(help_text="文件大小（字节）")
    file_ext = serializers.CharField(help_text="文件扩展名")
    file_url = serializers.CharField(help_text="文件访问URL")

class AttachmentListResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField(help_text="附件ID")
    file_name = serializers.CharField(help_text="存储文件名")
    origin_name = serializers.CharField(help_text="原始文件名")
    file_size = serializers.IntegerField(help_text="文件大小")
    file_ext = serializers.CharField(help_text="文件扩展名")
    upload_by_name = serializers.CharField(help_text="上传人姓名")
    created_at = serializers.CharField(help_text="上传时间")


class AttachmentDetailResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField(help_text="附件ID")
    file_name = serializers.CharField(help_text="存储文件名")
    origin_name = serializers.CharField(help_text="原始文件名")
    file_size = serializers.IntegerField(help_text="文件大小")
    file_ext = serializers.CharField(help_text="文件扩展名")
    upload_by_name = serializers.CharField(help_text="上传人姓名")
    created_at = serializers.CharField(help_text="上传时间")


class AttachmentBase64UploadSerializer(serializers.Serializer):
    name = serializers.CharField(required=True, help_text="文件名，如 图片.jpg")
    content = serializers.CharField(required=True, help_text="Base64编码的文件内容")
    extension = serializers.CharField(required=False, allow_blank=True, help_text="文件扩展名，如 .jpg")
