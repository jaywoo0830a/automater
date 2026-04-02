"""
api/__main__.py
----------------
python -m api 로 서버 실행.

    python -m api                    # 0.0.0.0:5000
    python -m api --port 8080        # 0.0.0.0:8080
    API_KEY=mykey python -m api      # API key 인증 활성화
"""

import argparse

from api.app import app


def main():
    parser = argparse.ArgumentParser(prog="python -m api")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
