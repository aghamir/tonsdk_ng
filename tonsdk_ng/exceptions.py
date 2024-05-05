class TonSdkException(BaseException):
    """
    Base class for tonsdk exceptions.
    Subclasses should provide `.default_detail` properties.
    """

    default_detail = "TonSdk error."

    def __init__(self, detail: str | None = None):
        super().__init__()
        self.detail = self.default_detail if detail is None else detail

    def __str__(self) -> str:
        return str(self.detail)


class InvalidAddressError(TonSdkException):
    default_detail = "Invalid address error."
