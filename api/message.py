from django.utils.translation import gettext

class ResponseMessage:
    def __init__(self, message: str, code: int = 200):
        self.message = message
        self.code = code

    def to_dict(self):
        return {"message": self.message, "code": self.code}
class ResponseList:
    def __init__(self, results: list | None = None, count: int = 0, code: int = 200):
        message = message or gettext("query_success")
        super().__init__(message, code)
        self.count = count
        self.results = results or []

    def to_dict(self):
        return { "code": self.code, "count": self.count, "results": self.results}
