# 雪花算法实现（简化版，适合单机/开发环境）
import threading
import time

class Snowflake:
    def __init__(self, datacenter_id=0, worker_id=0):
        self.datacenter_id = datacenter_id & 0x1F  # 5 bits
        self.worker_id = worker_id & 0x1F          # 5 bits
        self.sequence = 0
        self.last_timestamp = -1
        self.lock = threading.Lock()

    def _timestamp(self):
        return int(time.time() * 1000)

    def get_id(self):
        with self.lock:
            timestamp = self._timestamp()
            if timestamp == self.last_timestamp:
                self.sequence = (self.sequence + 1) & 0xFFF  # 12 bits
                if self.sequence == 0:
                    while timestamp <= self.last_timestamp:
                        timestamp = self._timestamp()
            else:
                self.sequence = 0
            self.last_timestamp = timestamp
            id = ((timestamp - 1288834974657) << 22) | (self.datacenter_id << 17) | (self.worker_id << 12) | self.sequence
            return id

# 单例
_snowflake = Snowflake()
def generate_snowflake_id():
    return _snowflake.get_id()
