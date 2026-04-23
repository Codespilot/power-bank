import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from rest_framework import status
from rest_framework.generics import ListAPIView
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from .models import Order, OrderImport
from .order_serializers import OrderSerializer, OrderImportSerializer

logger = logging.getLogger(__name__)

class OrderListView(ListAPIView):
    """商户订单分页查询接口，支持关键字与日期范围筛选。"""

    serializer_class = OrderSerializer

    def get_queryset(self):
        qs = Order.objects.all().order_by('-id')
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


from rest_framework.permissions import AllowAny
from utils.generate_snowflake_id import generate_snowflake_id
from api.import_tasks import start_import_task
from api.profit_tasks import (
    rollback_profit_allocation_for_import,
    run_profit_allocation_with_tracking,
)

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

        order_import = OrderImport.objects.create(
            id=generate_snowflake_id(),
            file_name=file.name,
            status=OrderImport.STATUS_RUNNING,
            profit_task_status=OrderImport.PROFIT_STATUS_NOT_STARTED,
            created_at=timezone.now()
        )
        # 启动后台任务处理Excel
        start_import_task(order_import.id, file)
        return Response({'id': str(order_import.id)})


class OrderImportRunProfitView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, id):
        order_import = OrderImport.objects.filter(id=id).first()
        if not order_import:
            return Response({'message': '导入记录不存在'}, status=404)

        if order_import.status == OrderImport.STATUS_RUNNING:
            return Response({'message': '导入任务仍在运行，暂不可执行分润'}, status=400)

        if order_import.failed_rows and order_import.failed_rows > 0:
            return Response({'message': '导入存在失败行，不能执行分润'}, status=400)

        if order_import.profit_task_status == OrderImport.PROFIT_STATUS_RUNNING:
            return Response({'message': '分润任务正在运行'}, status=400)

        result = run_profit_allocation_with_tracking(order_import_id=order_import.id)
        latest = OrderImport.objects.filter(id=order_import.id).first()
        if latest and latest.profit_task_status == OrderImport.PROFIT_STATUS_FAILED:
            return Response({'message': latest.profit_error_message or '分润任务执行失败'}, status=500)

        return Response({'message': '分润任务执行完成', 'result': result})


class OrderImportDetailView(APIView):
    permission_classes = [AllowAny]

    def delete(self, request, id):
        order_import = OrderImport.objects.filter(id=id).first()
        if not order_import:
            return Response({'message': '导入记录不存在'}, status=404)

        if order_import.status == OrderImport.STATUS_RUNNING:
            return Response({'message': '导入任务正在运行，不能删除'}, status=400)
        if order_import.profit_task_status == OrderImport.PROFIT_STATUS_RUNNING:
            return Response({'message': '分润任务正在运行，不能删除'}, status=400)

        with transaction.atomic():
            rollback_result = rollback_profit_allocation_for_import(order_import.id)
            deleted_orders, _ = Order.objects.filter(import_id=order_import.id).delete()
            order_import.delete()

        return Response(
            {
                'message': '导入记录已删除',
                'deleted_order_rows': int(deleted_orders or 0),
                **rollback_result,
            }
        )

class OrderImportRunningCountView(APIView):
    """返回当前仍在执行中的导入任务数量。"""

    def get(self, request):
        count = OrderImport.objects.filter(status=OrderImport.STATUS_RUNNING).count()
        return Response({'count': count})
