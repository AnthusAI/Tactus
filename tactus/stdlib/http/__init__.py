"""Standard library HTTP tool for Tactus.

Provides HTTP request utilities that agents can use.
"""

import json
from typing import Optional, Dict, Any, Literal
from urllib.parse import urlencode
import urllib.request
import urllib.error


def http(
    url: str,
    method: Literal["GET", "POST", "PUT", "DELETE", "HEAD"] = "GET",
    headers: Optional[Dict[str, str]] = None,
    body: Optional[Any] = None,
    params: Optional[Dict[str, str]] = None,
    json_body: Optional[Any] = None,
    timeout: int = 30,
) -> dict:
    """Make an HTTP request.

    Args:
        url: The URL to request
        method: HTTP method (GET, POST, PUT, DELETE, HEAD)
        headers: Optional headers dict
        body: Optional request body (string)
        params: Optional query parameters dict
        json_body: Optional JSON body (will be serialized)
        timeout: Request timeout in seconds

    Returns:
        Dict with status, response data, and metadata

    Examples:
        >>> http("https://api.example.com/data")
        {'status': 'success', 'code': 200, 'data': '...', 'headers': {...}}

        >>> http("https://api.example.com/users", method="POST", json_body={"name": "Alice"})
        {'status': 'success', 'code': 201, 'data': {...}, 'headers': {...}}
    """
    try:
        # Build URL with query parameters
        if params:
            query_string = urlencode(params)
            separator = "&" if "?" in url else "?"
            full_url = f"{url}{separator}{query_string}"
        else:
            full_url = url

        # Prepare headers
        req_headers = headers or {}

        # Prepare body
        req_body = None
        if json_body is not None:
            req_body = json.dumps(json_body).encode("utf-8")
            req_headers["Content-Type"] = "application/json"
        elif body is not None:
            if isinstance(body, str):
                req_body = body.encode("utf-8")
            else:
                req_body = body

        # Create request
        request = urllib.request.Request(
            full_url, data=req_body, headers=req_headers, method=method
        )

        # Make the request
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                # Read response
                response_data = response.read()

                # Try to decode as text
                try:
                    response_text = response_data.decode("utf-8")
                except UnicodeDecodeError:
                    response_text = None

                # Try to parse as JSON
                response_json = None
                if response_text and response.headers.get("Content-Type", "").startswith(
                    "application/json"
                ):
                    try:
                        response_json = json.loads(response_text)
                    except json.JSONDecodeError:
                        pass

                return {
                    "status": "success",
                    "code": response.code,
                    "data": response_json if response_json is not None else response_text,
                    "headers": dict(response.headers),
                    "url": full_url,
                    "method": method,
                }

        except urllib.error.HTTPError as e:
            # HTTP error (4xx, 5xx)
            error_data = None
            try:
                error_body = e.read().decode("utf-8")
                try:
                    error_data = json.loads(error_body)
                except json.JSONDecodeError:
                    error_data = error_body
            except Exception:
                pass

            return {
                "status": "error",
                "code": e.code,
                "error": f"HTTP {e.code}: {e.reason}",
                "data": error_data,
                "url": full_url,
                "method": method,
            }

        except urllib.error.URLError as e:
            # Network error
            return {
                "status": "error",
                "error": f"Network error: {str(e.reason)}",
                "url": full_url,
                "method": method,
            }

    except Exception as e:
        return {"status": "error", "error": str(e), "url": url, "method": method}


def get(url: str, **kwargs) -> dict:
    """Make a GET request.

    Convenience wrapper for http() with method="GET".

    Args:
        url: The URL to request
        **kwargs: Additional arguments for http()

    Returns:
        Result from http()
    """
    return http(url, method="GET", **kwargs)


def post(url: str, **kwargs) -> dict:
    """Make a POST request.

    Convenience wrapper for http() with method="POST".

    Args:
        url: The URL to request
        **kwargs: Additional arguments for http()

    Returns:
        Result from http()
    """
    return http(url, method="POST", **kwargs)


def put(url: str, **kwargs) -> dict:
    """Make a PUT request.

    Convenience wrapper for http() with method="PUT".

    Args:
        url: The URL to request
        **kwargs: Additional arguments for http()

    Returns:
        Result from http()
    """
    return http(url, method="PUT", **kwargs)


def delete(url: str, **kwargs) -> dict:
    """Make a DELETE request.

    Convenience wrapper for http() with method="DELETE".

    Args:
        url: The URL to request
        **kwargs: Additional arguments for http()

    Returns:
        Result from http()
    """
    return http(url, method="DELETE", **kwargs)


# Export all HTTP functions
__all__ = ["http", "get", "post", "put", "delete"]
