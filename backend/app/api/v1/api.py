"""
Основной роутер API v1
Подключает все endpoints
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, quests, wallet, notifications, badges, admin, classes

# Создаём главный роутер для версии API v1
api_router = APIRouter()

# Подключаем endpoints
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(quests.router)
api_router.include_router(wallet.router)
api_router.include_router(notifications.router)
api_router.include_router(badges.router)
api_router.include_router(admin.router)
api_router.include_router(classes.router)
