"""Video-Capture CLI — 委托给 src.cli。"""
import uvicorn

from src.api.app import create_app

app= create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8090)
