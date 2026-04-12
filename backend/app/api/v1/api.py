"""
Основной роутер API v1
Подключает все endpoints
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
	admin,
	admin_runtime,
	analytics,
	auth,
	badges,
	challenges,
	classes,
	counter_offers,
	disputes,
	events,
	leads,
	learning,
	lifecycle,
	marketplace,
	meta,
	messages,
	milestones,
	notifications,
	quests,
	referrals,
	reviews,
	saved_searches,
	shortlists,
	templates,
	users,
	wallet,
)

# Создаём главный роутер для версии API v1
api_router = APIRouter()

# Подключаем endpoints
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(quests.router)
api_router.include_router(disputes.router)
api_router.include_router(disputes.admin_router)
api_router.include_router(wallet.router)
api_router.include_router(notifications.router)
api_router.include_router(badges.router)
api_router.include_router(admin.router)
api_router.include_router(admin_runtime.router)
api_router.include_router(classes.router)
api_router.include_router(leads.router)
api_router.include_router(marketplace.router)
api_router.include_router(meta.router)
api_router.include_router(messages.router)
api_router.include_router(reviews.router)
api_router.include_router(shortlists.router)
api_router.include_router(templates.router)
api_router.include_router(analytics.router)
api_router.include_router(lifecycle.router)
api_router.include_router(saved_searches.router)
api_router.include_router(events.router)
api_router.include_router(events.admin_events_router)
api_router.include_router(learning.router)
api_router.include_router(counter_offers.router)
api_router.include_router(milestones.router)
api_router.include_router(challenges.router)
api_router.include_router(referrals.router)
