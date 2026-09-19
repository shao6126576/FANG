from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import router as api_router
from app.core.config import settings
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="医疗保险知识图谱问答系统",
    description="基于 Neo4j 和 Qwen 的智能保险问答系统",
    version="1.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router, prefix="/api/v1")

# 静态文件配置
app.mount("/", StaticFiles(directory=".", html=True), name="static")

@app.get("/")
async def root():
    return {"message": "医疗保险知识图谱问答系统 API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG
    )