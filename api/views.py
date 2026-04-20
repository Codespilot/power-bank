from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Item
from .serializers import ItemSerializer


class HealthCheckView(APIView):
    """最小健康检查接口，用于确认服务是否正常运行。"""

    def get(self, request):
        return Response({"status": "ok", "service": "power-bank-api"})


class ItemListCreateView(generics.ListCreateAPIView):
    """示例条目接口，保留基础的增删查改演示能力。"""

    queryset = Item.objects.order_by("-created_at")
    serializer_class = ItemSerializer

