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
