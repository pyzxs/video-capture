"""Video-Capture CLI — 委托给 src.cli。"""
import uvicorn


if __name__ == "__main__":
    uvicorn.run("src.api.app:app", host="127.0.0.1", port=8090)
