import logging
import os
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime


class LevelFilter(logging.Filter):
    """只允许指定级别的日志通过。"""

    def __init__(self, level: int):
        super().__init__()
        self._level = level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno == self._level


class DatedFileHandler(TimedRotatingFileHandler):
    """日志文件名包含日期的轮转处理器。

    生成 debug-2026-04-24.log 格式的文件名，每日轮转。
    """

    def __init__(self, filename, when="midnight", backupCount=30,
                 encoding="utf-8", formatter=None):
        self._base = filename
        self._log_dir = os.path.dirname(filename)
        self._basename = os.path.basename(filename)
        self._name_root = self._basename[:-4] if self._basename.endswith(".log") else self._basename
        # 去掉 .log 后缀用于构建日期文件名
        self._name_root = self._basename[:-4] if self._basename.endswith(".log") else self._basename
        filename = self._date_filename()
        super().__init__(
            filename=filename,
            when=when,
            backupCount=backupCount,
            encoding=encoding,
        )

    def _date_filename(self):
        return os.path.join(
            self._log_dir,
            f"{self._name_root}-{datetime.now().strftime('%Y-%m-%d')}.log",
        )

    def doRollover(self):
        self.baseFilename = self._date_filename()
        # 新文件从开头写，不继承旧内容
        if os.path.exists(self.baseFilename):
            os.remove(self.baseFilename)
        super().doRollover()
