from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"

    def ready(self):
        import api.signals  # 导入信号处理器，确保它们被注册
        from .profit.profit_tasks import start_profit_scheduler

        start_profit_scheduler()
