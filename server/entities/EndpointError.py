

class EndpointStatusError(Exception):
    def __init__(self, service: str, status_code: int, message: str, response_body: str = ""):
        self.service = service
        self.status_code = status_code
        self.message = message
        self.response_body = response_body
        super().__init__(f"{service}: {message}")

def raise_endpoint_status(response, service: str) -> None:
    """
    Check response status and raise EndpointStatusError if status >= 400.
    Uses raise_for_status() internally and catches it to re-raise with service context.
    """
    try:
        # Try the built-in raise_for_status
        response.raise_for_status()
    except Exception as e:
        # This catches HTTPError, HTTPStatusError, etc.
        # Now re-raise with our custom exception and service context
        raise EndpointStatusError(
            service=service,
            status_code=response.status_code,
            message=str(e) if str(e) else f"HTTP {response.status_code}",
            response_body=response.text[:500] if hasattr(response, 'text') else str(response.content)
        )
