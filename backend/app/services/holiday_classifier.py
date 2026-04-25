from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Dict, List, Optional, Tuple

from app.db.models import Client, Holiday


class HolidayCategory(Enum):
    """Категории праздников"""

    PERSONAL = "personal"  # День рождения
    NATIONAL = "national"  # Государственные
    PROFESSIONAL = "professional"  # Профессиональные
    INDUSTRY = "industry"  # Отраслевые
    SEASONAL = "seasonal"  # Сезонные (Новый год)
    PROMOTIONAL = "promotional"  # Маркетинговые акции


class AudienceType(Enum):
    """Тип аудитории праздника"""

    ALL = "all"
    GENDER_BASED = "gender_based"
    ROLE_BASED = "role_based"
    OKVED_BASED = "okved_based"
    INTEREST_BASED = "interest_based"


class HolidayClassifier:
    """Классификатор праздников для фильтрации, приоритизации и персонализации"""

    def __init__(self, client: Optional[Client] = None):
        self.client = client
        self._client_profession = client.profession if client else None
        self._client_okved = client.okved_code if client else None

    def classify_holiday(self, holiday: Holiday) -> Tuple[HolidayCategory, AudienceType]:
        """Определяет категорию и тип аудитории праздника"""
        tags = holiday.tags or {}

        # Определяем категорию
        category_str = tags.get("category", "general")
        category_map = {
            "personal": HolidayCategory.PERSONAL,
            "national": HolidayCategory.NATIONAL,
            "professional": HolidayCategory.PROFESSIONAL,
            "industry": HolidayCategory.INDUSTRY,
            "seasonal": HolidayCategory.SEASONAL,
            "promotional": HolidayCategory.PROMOTIONAL,
        }
        category = category_map.get(category_str, HolidayCategory.SEASONAL)

        # Определяем тип аудитории
        audience = tags.get("audience", "all")
        audience_map = {
            "all": AudienceType.ALL,
            "gender_based": AudienceType.GENDER_BASED,
            "role_based": AudienceType.ROLE_BASED,
            "okved_based": AudienceType.OKVED_BASED,
            "interest_based": AudienceType.INTEREST_BASED,
        }
        audience_type = audience_map.get(audience, AudienceType.ALL)

        return category, audience_type

    def is_applicable_to_client(self, holiday: Holiday) -> bool:
        """Проверяет, применим ли праздник к данному клиенту"""
        if not self.client:
            return True

        tags = holiday.tags or {}
        audience = tags.get("audience", "all")

        # Проверка по профессии
        if audience == "role_based":
            required_profession = tags.get("profession")
            if required_profession and required_profession != self._client_profession:
                return False

        # Проверка по ОКВЭД
        if audience == "okved_based":
            okved_tags = tags.get("okved_tags", [])
            if okved_tags and self._client_okved:
                okved_root = self._client_okved[:2]
                if not any(
                    tag == "all"
                    or tag == okved_root
                    or (tag.endswith(".") and self._client_okved.startswith(tag))
                    for tag in okved_tags
                ):
                    return False

        return True

    def get_priority(self, holiday: Holiday) -> int:
        """Возвращает приоритет праздника (из tags; без сегментации клиентов)."""
        tags = holiday.tags or {}
        return int(tags.get("priority", 5) or 5)

    def get_suggested_channel(self, holiday: Holiday) -> str:
        """Рекомендует канал отправки для данного праздника"""
        category, _ = self.classify_holiday(holiday)

        # Массовые праздники можно отправлять SMS
        if category == HolidayCategory.NATIONAL:
            return "sms"

        # Профессиональные праздники - email (можно с картинкой)
        if category == HolidayCategory.PROFESSIONAL:
            return "email"

        # По умолчанию - предпочтительный канал клиента
        if self.client and hasattr(self.client, "preferred_channel"):
            return self.client.preferred_channel or "email"

        return "email"

    def filter_by_consent(self, holiday: Holiday, client_consents: dict) -> bool:
        """Фильтрует праздники по согласиям клиента"""
        category, _ = self.classify_holiday(holiday)

        # Маркетинговые праздники требуют специального согласия
        if category == HolidayCategory.PROMOTIONAL:
            return client_consents.get("personalized_offers", False)

        # Остальные всегда можно
        return True

    def get_personalization_context(self, holiday: Holiday) -> dict:
        """Возвращает контекст для персонализации поздравления"""
        tags = holiday.tags or {}
        category, audience = self.classify_holiday(holiday)

        context = {
            "category": category.value,
            "audience_type": audience.value,
            "tone_hint": tags.get("tone_hint", "warm"),
            "focus_hint": tags.get("focus_hint", "general"),
            "prompt_hint": tags.get("prompt_hint", ""),
            "suggested_gift": tags.get("metadata", {}).get("suggested_gift"),
            "industry": tags.get("metadata", {}).get("industry"),
        }

        # Добавляем персональные данные клиента
        if self.client:
            context["client_name"] = self.client.first_name
            if self._client_profession:
                context["profession"] = self._client_profession

        return context


class HolidayBatchClassifier:
    """Классификатор для массовой обработки праздников"""

    def __init__(self, session):
        self.session = session

    async def get_holidays_for_period(
        self, start_date: dt.date, end_date: dt.date, category: Optional[str] = None
    ) -> List[Holiday]:
        """Возвращает праздники за период с возможной фильтрацией по категории"""
        from sqlalchemy import select

        query = (
            select(Holiday)
            .where(Holiday.date >= start_date, Holiday.date <= end_date)
            .order_by(Holiday.date)
        )

        result = await self.session.execute(query)
        holidays = result.scalars().all()
        if not category:
            return holidays
        # Категория хранится в Holiday.tags["category"].
        return [h for h in holidays if ((h.tags or {}).get("category") or "general") == category]

    async def get_holidays_grouped_by_category(
        self, start_date: dt.date, end_date: dt.date
    ) -> Dict[str, List[Holiday]]:
        """Группирует праздники по категориям"""
        holidays = await self.get_holidays_for_period(start_date, end_date)

        grouped = {}
        for holiday in holidays:
            tags = holiday.tags or {}
            category = tags.get("category", "general")
            if category not in grouped:
                grouped[category] = []
            grouped[category].append(holiday)

        return grouped

    async def get_upcoming_holidays(self, days_ahead: int = 7) -> List[Holiday]:
        """Возвращает предстоящие праздники"""
        today = dt.date.today()
        end_date = today + dt.timedelta(days=days_ahead)
        return await self.get_holidays_for_period(today, end_date)

    async def get_holidays_stats(self, year: int) -> Dict:
        """Возвращает статистику по праздникам за год"""
        start_date = dt.date(year, 1, 1)
        end_date = dt.date(year, 12, 31)

        holidays = await self.get_holidays_for_period(start_date, end_date)

        stats = {
            "total": len(holidays),
            "by_category": {},
            "by_month": {i: 0 for i in range(1, 13)},
            "professional_count": 0,
            "national_count": 0,
            "seasonal_count": 0,
        }

        for holiday in holidays:
            tags = holiday.tags or {}
            category = tags.get("category", "general")
            stats["by_category"][category] = stats["by_category"].get(category, 0) + 1

            month = holiday.date.month
            stats["by_month"][month] = stats["by_month"].get(month, 0) + 1

            if category == "professional":
                stats["professional_count"] += 1
            elif category == "national":
                stats["national_count"] += 1
            elif category == "seasonal":
                stats["seasonal_count"] += 1

        return stats
