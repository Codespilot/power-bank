import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from rest_framework import status
from rest_framework.generics import ListAPIView, CreateAPIView
from django.utils import timezone
from django.db.models import Q
from .models import MerchantOrder, OrderImport
from .order_serializers import MerchantOrderSerializer, OrderImportSerializer

logger = logging.getLogger(__name__)

class MerchantOrderListView(ListAPIView):
    """商户订单分页查询接口，支持关键字与日期范围筛选。"""

    serializer_class = MerchantOrderSerializer

    def get_queryset(self):
        qs = MerchantOrder.objects.all().order_by('-id')
        kw = str(self.request.GET.get('kw') or self.request.GET.get('keyword') or '').strip()
        date_start = self.request.GET.get('date_start')
        date_end = self.request.GET.get('date_end')

        if kw:
            qs = qs.filter(Q(merchant_name__icontains=kw) | Q(order_no__icontains=kw))
        if date_start:
            qs = qs.filter(order_date__gte=date_start)
        if date_end:
            qs = qs.filter(order_date__lte=date_end)

        return qs


# 合并 GET/POST 到同一个视图
from rest_framework.permissions import AllowAny
from config.import_map import get_import_column_mapping
from utils.generate_snowflake_id import generate_snowflake_id
from api.import_tasks import start_import_task

class OrderImportListCreateView(APIView):
    """订单导入任务接口。

    GET 返回导入历史；POST 仅创建导入任务，实际文件解析由后台线程完成。
    """
    parser_classes = [MultiPartParser]
    permission_classes = [AllowAny]

    def get(self, request):
        qs = OrderImport.objects.all().order_by('-id')
        date_start = request.GET.get('date_start')
        date_end = request.GET.get('date_end')
        if date_start:
            qs = qs.filter(created_at__gte=date_start)
        if date_end:
            qs = qs.filter(created_at__lte=date_end)

        # 分页
        from rest_framework.pagination import PageNumberPagination
        paginator = PageNumberPagination()
        paginator.page_size_query_param = 'page_size'
        page = paginator.paginate_queryset(qs, request)
        serializer = OrderImportSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'message': '未上传文件'}, status=400)

        # 获取列名到字段名的映射
        column_mapping = get_import_column_mapping()

        # TODO: 这里应解析Excel/CSV文件，按column_mapping将表头列名转换为字段名
        # 示例伪代码：
        # import pandas as pd
        # df = pd.read_excel(file)
        # df.rename(columns=column_mapping, inplace=True)
        # ...后续处理...

        order_import = OrderImport.objects.create(
            id=generate_snowflake_id(),
            file_name=file.name,
            status=OrderImport.STATUS_RUNNING,
            created_at=timezone.now()
        )
        # 启动后台任务处理Excel
        start_import_task(order_import.id, file)
        return Response({'id': str(order_import.id)})

class OrderImportRunningCountView(APIView):
    """返回当前仍在执行中的导入任务数量。"""

    def get(self, request):
        count = OrderImport.objects.filter(status=OrderImport.STATUS_RUNNING).count()
        return Response({'count': count})
