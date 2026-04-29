from rest_framework import serializers


# ============ 协议管理 Request/Response Serializers ============

class TermListRequestSerializer(serializers.Serializer):
    keyword = serializers.CharField(required=False, allow_blank=True, help_text="关键字，搜索名称")
    type = serializers.IntegerField(required=False, help_text="协议类型：1-隐私政策、2-用户协议")
    platform = serializers.IntegerField(required=False, help_text="平台：1-全部、2-Web、3-小程序、4-App、5-其他")
    page = serializers.IntegerField(required=False, default=1, help_text="页码")
    limit = serializers.IntegerField(required=False, default=10, help_text="每页数量")


class TermListResponseSerializer(serializers.Serializer):
    id = serializers.CharField(help_text="协议ID")
    name = serializers.CharField(help_text="协议名称")
    type = serializers.IntegerField(help_text="协议类型")
    type_name = serializers.CharField(help_text="协议类型名称")
    platform = serializers.IntegerField(help_text="平台")
    platform_name = serializers.CharField(help_text="平台名称")
    file_name = serializers.CharField(allow_null=True, help_text="文件名")
    status = serializers.IntegerField(help_text="状态")
    status_name = serializers.CharField(help_text="状态名称")
    created_at = serializers.CharField(help_text="创建时间")
    published_at = serializers.CharField(allow_null=True, help_text="发布时间")


class TermDetailResponseSerializer(serializers.Serializer):
    id = serializers.CharField(help_text="协议ID")
    name = serializers.CharField(help_text="协议名称")
    type = serializers.IntegerField(help_text="协议类型")
    platform = serializers.IntegerField(help_text="平台")
    content = serializers.CharField(help_text="协议内容")
    file_name = serializers.CharField(allow_null=True, help_text="文件名")
    status = serializers.IntegerField(help_text="状态")
    created_at = serializers.CharField(help_text="创建时间")
    updated_at = serializers.CharField(help_text="修改时间")
    published_at = serializers.CharField(allow_null=True, help_text="发布时间")


class TermCreateRequestSerializer(serializers.Serializer):
    name = serializers.CharField(required=True, max_length=50, help_text="协议名称，最长50字")
    type = serializers.IntegerField(required=True, help_text="协议类型：1-隐私政策、2-用户协议")
    platform = serializers.IntegerField(required=True, help_text="平台：1-全部、2-Web、3-小程序、4-App、5-其他")
    content = serializers.CharField(required=True, help_text="协议内容，支持html和markdown格式")


class TermUpdateRequestSerializer(serializers.Serializer):
    name = serializers.CharField(required=True, max_length=50, help_text="协议名称，最长50字")
    type = serializers.IntegerField(required=True, help_text="协议类型：1-隐私政策、2-用户协议")
    platform = serializers.IntegerField(required=True, help_text="平台：1-全部、2-Web、3-小程序、4-App、5-其他")
    content = serializers.CharField(required=True, help_text="协议内容，支持html和markdown格式")


class TermPublicResponseSerializer(serializers.Serializer):
    name = serializers.CharField(help_text="协议名称")
    content = serializers.CharField(help_text="协议内容（html格式）")
    publish_time = serializers.CharField(help_text="发布时间")
