"""
api/auth.py
-----------
API key 인증 미들웨어.

환경변수 API_KEY가 설정되어 있으면 요청 헤더 X-API-Key와 비교한다.
설정되지 않으면 인증을 건너뛴다.
"""

from __future__ import annotations

import os
from functools import wraps

from flask import request, jsonify


def require_api_key(f):
    """API key 헤더 검증 데코레이터."""
    @wraps(f)
    def decorated(*args, **kwargs):
        expected = os.environ.get("API_KEY", "")
        if not expected:
            return f(*args, **kwargs)

        provided = request.headers.get("X-API-Key", "")
        if provided != expected:
            return jsonify({"error": "Invalid or missing API key"}), 401

        return f(*args, **kwargs)
    return decorated
