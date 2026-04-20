from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Item
from .serializers import ItemSerializer


class HealthCheckView(APIView):
    def get(self, request):
        return Response({"status": "ok", "service": "power-bank-api"})


class ItemListCreateView(generics.ListCreateAPIView):
    queryset = Item.objects.order_by("-created_at")
    serializer_class = ItemSerializer

