from django.db import models
from rest_framework import serializers

from .models import Item


class BigIntStringField(serializers.IntegerField):
    def to_representation(self, value):
        if value is None:
            return None
        return str(value)


class SafeBigIntModelSerializer(serializers.ModelSerializer):
    serializer_field_mapping = serializers.ModelSerializer.serializer_field_mapping.copy()
    serializer_field_mapping[models.BigIntegerField] = BigIntStringField
    serializer_field_mapping[models.BigAutoField] = BigIntStringField


class ItemSerializer(SafeBigIntModelSerializer):
    class Meta:
        model = Item
        fields = ["id", "name", "description", "created_at"]
        read_only_fields = ["id", "created_at"]


class GenericResponseSerializer(serializers.Serializer):
    """分页列表响应的通用 Serializer。

    通过下标语法生成具体类型，用于 extend_schema 文档注解::

        @extend_schema(responses={200: GenericResponseSerializer[UserListSerializer]})
        class UserListView(generics.ListAPIView): ...
    """

    count = serializers.IntegerField(help_text="总条数")
    next = serializers.CharField(allow_null=True, help_text="下一页链接")
    previous = serializers.CharField(allow_null=True, help_text="上一页链接")
    results = serializers.ListField(help_text="数据列表")
    message = serializers.CharField(help_text="响应消息")

    def __class_getitem__(cls, result_serializer_class: type[serializers.Serializer]) -> type[serializers.Serializer]:
        """支持 GenericResponseSerializer[SomeSerializer] 语法，返回具体化的 Serializer 类。"""

        class _PaginatedResponse(serializers.Serializer):
            count = serializers.IntegerField(help_text="总条数")
            next = serializers.CharField(allow_null=True, help_text="下一页链接")
            previous = serializers.CharField(allow_null=True, help_text="上一页链接")
            results = result_serializer_class(many=True)
            message = serializers.CharField(help_text="响应消息")

        _PaginatedResponse.__name__ = f"Paginated{result_serializer_class.__name__}"
        _PaginatedResponse.__qualname__ = f"Paginated{result_serializer_class.__name__}"
        return _PaginatedResponse
