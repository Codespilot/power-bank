from rest_framework import serializers


class BankCardListRequestSerializer(serializers.Serializer):
    page = serializers.IntegerField(required=False, default=1, help_text="页码")
    limit = serializers.IntegerField(required=False, default=10, help_text="每页数量")
    keyword = serializers.CharField(required=False, allow_blank=True, help_text="搜索关键词")


class BankCardLookupSerializer(serializers.Serializer):
    id = serializers.CharField(help_text="银行卡ID")
    card_no = serializers.CharField(help_text="银行卡号")
    name = serializers.CharField(help_text="持卡人姓名")


class BankCardListResponseSerializer(serializers.Serializer):
    id = serializers.CharField(help_text="银行卡ID")
    card_no = serializers.CharField(help_text="银行卡号")
    name = serializers.CharField(help_text="持卡人姓名")
    id_no = serializers.CharField(help_text="身份证号（隐藏中间6位）")
    mobile = serializers.CharField(help_text="预留手机号")
    card_photo_url = serializers.CharField(allow_blank=True, help_text="银行卡照片URL")
    id_photo_badge_url = serializers.CharField(allow_blank=True, help_text="身份证国徽照片URL")
    id_photo_face_url = serializers.CharField(allow_blank=True, help_text="身份证人像照片URL")
    is_default = serializers.BooleanField(help_text="是否默认")
    created_at = serializers.CharField(help_text="创建时间")


class BankCardDetailResponseSerializer(serializers.Serializer):
    id = serializers.CharField(help_text="银行卡ID")
    card_no = serializers.CharField(help_text="银行卡号")
    name = serializers.CharField(help_text="持卡人姓名")
    id_no = serializers.CharField(help_text="身份证号（隐藏中间6位）")
    mobile = serializers.CharField(help_text="预留手机号")
    card_photo = serializers.CharField(allow_blank=True, help_text="银行卡照片文件名")
    card_photo_url = serializers.CharField(allow_blank=True, help_text="银行卡照片URL")
    id_photo_badge = serializers.CharField(allow_blank=True, help_text="身份证国徽照片文件名")
    id_photo_badge_url = serializers.CharField(allow_blank=True, help_text="身份证国徽照片URL")
    id_photo_face = serializers.CharField(allow_blank=True, help_text="身份证人像照片文件名")
    id_photo_face_url = serializers.CharField(allow_blank=True, help_text="身份证人像照片URL")
    is_default = serializers.BooleanField(help_text="是否默认")
    user_id = serializers.CharField(help_text="用户ID")
    created_at = serializers.CharField(help_text="创建时间")


class BankCardCreateRequestSerializer(serializers.Serializer):
    card_no = serializers.CharField(help_text="银行卡号")
    name = serializers.CharField(help_text="持卡人姓名")
    id_no = serializers.CharField(help_text="身份证号")
    mobile = serializers.CharField(required=False, allow_blank=True, help_text="预留手机号")
    card_photo = serializers.CharField(required=False, allow_blank=True, help_text="银行卡照片文件名")
    id_photo_badge = serializers.CharField(required=False, allow_blank=True, help_text="身份证国徽照片文件名")
    id_photo_face = serializers.CharField(required=False, allow_blank=True, help_text="身份证人像照片文件名")
    is_default = serializers.BooleanField(required=False, default=False, help_text="是否默认")


class BankCardUpdateRequestSerializer(serializers.Serializer):
    card_no = serializers.CharField(required=False, help_text="银行卡号")
    name = serializers.CharField(required=False, help_text="持卡人姓名")
    id_no = serializers.CharField(required=False, help_text="身份证号")
    mobile = serializers.CharField(required=False, allow_blank=True, help_text="预留手机号")
    card_photo = serializers.CharField(required=False, help_text="银行卡照片文件名")
    id_photo_badge = serializers.CharField(required=False, help_text="身份证国徽照片文件名")
    id_photo_face = serializers.CharField(required=False, help_text="身份证人像照片文件名")
    is_default = serializers.BooleanField(required=False, help_text="是否默认")
