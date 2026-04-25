from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Holiday

log = logging.getLogger(__name__)


class HolidayLoader:
    """Загрузчик праздников из JSON-файлов в БД"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def load_from_json(self, json_path: Path, overwrite: bool = False) -> int:
        """
        Загружает праздники из JSON-файла
        
        Args:
            json_path: путь к JSON-файлу
            overwrite: перезаписывать ли существующие праздники
        
        Returns:
            количество загруженных праздников
        """
        if not json_path.exists():
            raise FileNotFoundError(f"JSON file not found: {json_path}")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        holidays_data = data.get('holidays', [])
        if not holidays_data:
            log.warning("No holidays found in JSON file")
            return 0
        
        count = 0
        
        for item in holidays_data:
            # Проверяем существование
            existing = await self._find_existing_holiday(
                item['date'], item['title']
            )
            
            if existing and not overwrite:
                continue
            
            if existing and overwrite:
                # Обновляем существующий
                await self._update_holiday(existing, item)
            else:
                # Создаём новый
                await self._create_holiday(item)
            
            count += 1
        
        await self.session.commit()
        log.info(f"Loaded {count} holidays from {json_path}")
        return count
    
    async def load_professional_holidays_from_catalog(self) -> int:
        """
        Загружает профессиональные праздники из holiday_catalog
        """
        from app.services.holiday_catalog import _PROFESSIONAL_HOLIDAYS, _calculate_floating_date
        
        count = 0
        current_year = dt.date.today().year
        
        for profession, rule in _PROFESSIONAL_HOLIDAYS.items():
            try:
                if rule.is_floating and rule.calculation_rule:
                    date_value = _calculate_floating_date(rule.calculation_rule, current_year)
                else:
                    date_value = dt.date(current_year, rule.month, rule.day)
                
                existing = await self._find_existing_holiday(
                    date_value.isoformat(), rule.title
                )
                
                if existing:
                    continue
                
                holiday = Holiday(
                    date=date_value,
                    title=rule.title,
                    tags={
                        **rule.tags,
                        "profession": profession,
                        "is_floating": rule.is_floating
                    },
                    category=rule.tags.get('category', 'professional'),
                    priority=rule.tags.get('priority', 5)
                )
                self.session.add(holiday)
                count += 1
                
            except Exception as e:
                log.error(f"Failed to load holiday {rule.title}: {e}")
        
        await self.session.commit()
        log.info(f"Loaded {count} professional holidays from catalog")
        return count
    
    async def load_general_holidays_from_catalog(self) -> int:
        """
        Загружает общие праздники из holiday_catalog
        """
        from app.services.holiday_catalog import _GENERAL_HOLIDAYS
        
        count = 0
        current_year = dt.date.today().year
        
        for rule in _GENERAL_HOLIDAYS:
            try:
                date_value = dt.date(current_year, rule.month, rule.day)
                
                existing = await self._find_existing_holiday(
                    date_value.isoformat(), rule.title
                )
                
                if existing:
                    continue
                
                holiday = Holiday(
                    date=date_value,
                    title=rule.title,
                    tags=rule.tags,
                    category=rule.tags.get('category', 'general'),
                    priority=rule.tags.get('priority', 5)
                )
                self.session.add(holiday)
                count += 1
                
            except Exception as e:
                log.error(f"Failed to load holiday {rule.title}: {e}")
        
        await self.session.commit()
        log.info(f"Loaded {count} general holidays from catalog")
        return count
    
    async def _find_existing_holiday(
        self, date_str: str, title: str
    ) -> Optional[Holiday]:
        """Находит существующий праздник по дате и названию"""
        result = await self.session.execute(
            select(Holiday).where(
                Holiday.date == dt.date.fromisoformat(date_str),
                Holiday.title == title
            )
        )
        return result.scalar_one_or_none()
    
    async def _create_holiday(self, item: Dict) -> None:
        """Создаёт новый праздник"""
        holiday = Holiday(
            date=dt.date.fromisoformat(item['date']),
            title=item['title'],
            tags=item.get('tags', {}),
            category=item.get('category', 'general'),
            priority=item.get('priority', 5)
        )
        self.session.add(holiday)
    
    async def _update_holiday(self, holiday: Holiday, item: Dict) -> None:
        """Обновляет существующий праздник"""
        holiday.tags = item.get('tags', holiday.tags)
        holiday.category = item.get('category', holiday.category)
        holiday.priority = item.get('priority', holiday.priority)
        self.session.add(holiday)
    
    async def get_all_holidays_for_year(self, year: int) -> List[Holiday]:
        """Возвращает все праздники на указанный год"""
        result = await self.session.execute(
            select(Holiday).where(
                Holiday.date >= dt.date(year, 1, 1),
                Holiday.date <= dt.date(year, 12, 31)
            ).order_by(Holiday.date)
        )
        return result.scalars().all()
    
    async def get_holidays_by_category(
        self, category: str, year: int
    ) -> List[Holiday]:
        """Возвращает праздники по категории"""
        result = await self.session.execute(
            select(Holiday).where(
                Holiday.category == category,
                Holiday.date >= dt.date(year, 1, 1),
                Holiday.date <= dt.date(year, 12, 31)
            ).order_by(Holiday.date)
        )
        return result.scalars().all()
    
    async def get_holidays_in_range(
        self, start_date: dt.date, end_date: dt.date
    ) -> List[Holiday]:
        """Возвращает праздники в указанном диапазоне дат"""
        result = await self.session.execute(
            select(Holiday).where(
                Holiday.date >= start_date,
                Holiday.date <= end_date
            ).order_by(Holiday.date)
        )
        return result.scalars().all()
    
    async def delete_old_holidays(self, before_year: int) -> int:
        """Удаляет праздники старше указанного года"""
        cutoff_date = dt.date(before_year, 1, 1)
        result = await self.session.execute(
            select(Holiday).where(Holiday.date < cutoff_date)
        )
        old_holidays = result.scalars().all()
        
        for holiday in old_holidays:
            await self.session.delete(holiday)
        
        await self.session.commit()
        return len(old_holidays)