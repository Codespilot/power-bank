from datetime import datetime, time as dt_time, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from blinker import signal
from django.db import transaction
from django.utils import timezone

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.exceptions import CredentialError
from api.message import ResponseMessage

import logging

logger = logging.getLogger(__name__)

_AMOUNT_QUANT = Decimal("0.01")


class HealthCheckView(APIView):
    """最小健康检查接口，用于确认服务是否正常运行。"""

    def get(self, request):
        return Response({"status": "ok", "service": "power-bank-api"})


class BaseAPIView(APIView):
    """API 基类，提供一些通用方法和属性，供其他 API 视图继承使用。"""

    def get_current_user_id(self, request):
        """从请求上下文中获取当前用户 ID，返回 None 表示未登录。"""
        from api.auth import get_request_user_id

        return get_request_user_id(request)

    def invoke(self, func: callable = None, *args, **kwargs) -> Response:
        try:
            return func(*args, **kwargs)
        except (InvalidOperation, TypeError, ValueError) as ve:
            logger.error(f"Error occurred: {ve}", exc_info=True)
            return Response(
                ResponseMessage(str(ve), 400).to_dict(),
                status=status.HTTP_400_BAD_REQUEST,
            )
        except PermissionError as pe:
            logger.error(f"Permission error: {pe}", exc_info=True)
            return Response(
                ResponseMessage(str(pe), 403).to_dict(),
                status=status.HTTP_403_FORBIDDEN,
            )
        except CredentialError as ce:
            logger.error(f"Credential error: {ce}", exc_info=True)
            return Response(
                ResponseMessage(str(ce), 401).to_dict(),
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            return Response(
                ResponseMessage(str(e), 500).to_dict(),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def build_common_response(self, data=None, message="成功", code=200):
        """构建统一格式的响应体。"""
        return Response({"code": code, "message": message, "data": data}, status=code)

    def build_list_response(self, results, count=None, message="成功", code=200):
        """构建分页列表响应体。"""
        return Response(
            {
                "code": code,
                "message": message,
                "count": count if count is not None else len(results),
                "next": "",
                "previous": "",
                "results": results,
            },
            status=code,
        )

    @classmethod
    def format_datetime(cls, value):
        """格式化日期时间为 ISO 8601 字符串。"""
        if not value:
            return "--"
        if timezone.is_naive(value):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return timezone.localtime(value).strftime("%Y-%m-%d %H:%M:%S")

    @classmethod
    def quantize_amount(cls, value) -> Decimal:
        return Decimal(str(value or 0)).quantize(_AMOUNT_QUANT, rounding=ROUND_HALF_UP)

    @classmethod
    def format_amount(cls, value) -> str:
        return format(cls.quantize_amount(value), "f")


def handle_request(func: callable = None, *args, **kwargs) -> Response:
    try:
        return func(*args, **kwargs)
    except (InvalidOperation, TypeError, ValueError) as ve:
        logger.error(f"Error occurred: {ve}", exc_info=True)
        return Response(
            ResponseMessage(str(ve), 400).to_dict(),
            status=status.HTTP_400_BAD_REQUEST,
        )
    except PermissionError as pe:
        logger.error(f"Permission error: {pe}", exc_info=True)
        return Response(
            ResponseMessage(str(pe), 403).to_dict(),
            status=status.HTTP_403_FORBIDDEN,
        )
    except CredentialError as ce:
        logger.error(f"Credential error: {ce}", exc_info=True)
        return Response(
            ResponseMessage(str(ce), 401).to_dict(),
            status=status.HTTP_401_UNAUTHORIZED,
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return Response(
            ResponseMessage(str(e), 500).to_dict(),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
