"""
QuestionWork Backend - FastAPI Application
IT-фриланс биржа с RPG-геймификацией
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

from app.api.v1.api import api_router


# Создаём FastAPI приложение
app = FastAPI(
    title=os.getenv("APP_NAME", "QuestionWork"),
    description="Backend для IT-фриланс биржи с RPG-геймификацией",
    version="0.1.0",
    debug=os.getenv("DEBUG", "False") == "True"
)

# Настраиваем CORS (разрешаем запросы с фронтенда)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Подключаем роутеры
app.include_router(api_router, prefix="/api/v1")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Проверка работоспособности API"""
    return {"status": "ok", "message": "QuestionWork API is running"}


# Root endpoint
@app.get("/")
async def root():
    """Приветственный endpoint"""
    return {
        "message": "Welcome to QuestionWork API",
        "docs": "/docs",
        "version": "0.1.0"
    }

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "False") == "True",
    )
