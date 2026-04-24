class ResponseMessage:
    def __init__(self, message: str, code: int = 200):
        self.message = message
        self.code = code

    def to_dict(self):
        return {"message": self.message, "code": self.code}
