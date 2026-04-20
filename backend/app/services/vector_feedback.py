import os
from datetime import datetime
from typing import List, Dict, Optional
import logging
from pathlib import Path
from dotenv import load_dotenv
from huggingface_hub import login
import chromadb
from sentence_transformers import SentenceTransformer
from app.core.config import settings

logger = logging.getLogger(__name__)
load_dotenv()

hf_token = os.getenv("HF_TOKEN")
if hf_token:
    login(token=hf_token)

class FeedbackVectorDB:
    def __init__(self, persist_directory: str = settings.vector_db_path):
        directory = Path(__file__).resolve().parents[2] / persist_directory
        os.makedirs(Path(directory), exist_ok=True)
        
        self.client = chromadb.PersistentClient(path=directory)
        self.encoder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        
        self.collection = self.client.get_or_create_collection(
            name="manager_feedback",
            metadata={"hnsw:space": "cosine"}
        )
        
        stats = self.get_statistics()
        logger.info(f"Векторная БД инициализирована. Хранится {stats['total']} примеров")
    
    def _get_embedding(self, text: str) -> List[float]:
        """Превращает текст в вектор чисел"""
        return self.encoder.encode(text).tolist()
    
    def save_feedback_vector(
        self,
        greeting_id: int,
        greeting_text: str,
        client_profession: str,
        holiday_title: str,
        rating: int,
        comment: str = "",
    ) -> str:
        if not client_profession:
            client_profession = "Неизвестно"
        """Сохраняет одобренное поздравление в векторную БД"""
        text_for_embedding = f"""
        Профессия клиента: {client_profession}
        Праздник: {holiday_title}
        Текст: {greeting_text}
        Комментарий: {comment}
        """
        
        doc_id = f"greeting_{greeting_id}_{datetime.now().timestamp()}"
        
        self.collection.add(
            ids=[doc_id],
            embeddings=[self._get_embedding(text_for_embedding)],
            metadatas=[{
                "greeting_id": greeting_id,
                "client_profession": client_profession,
                "holiday_title": holiday_title,
                "rating": rating,
                "created_at": datetime.now().isoformat()
            }],
            documents=[greeting_text]
        )
        
        logger.info(f"Сохранено в векторную БД: {client_profession} / {holiday_title} (оценка {rating}) {comment}")
        return doc_id
    
    def find_similar(
        self,
        client_profession: str,
        holiday_title: str,
        limit: int = 3,
        min_rating: int = 4
    ) -> List[Dict]:
        
        if self.collection.count() == 0:
            logger.debug("Векторная БД пуста")
            return []
        
        query_text = f"""
        Профессия клиента: {client_profession}
        Праздник: {holiday_title}
        """
        
        try:
            results = self.collection.query(
                query_embeddings=[self._get_embedding(query_text)],
                n_results=min(limit, self.collection.count()),
                where={
                    "$and": [
                        {"client_profession": client_profession},
                        {"holiday_title": holiday_title},
                        {"rating": {"$gte": min_rating}}
                    ]
                }
            )
        except Exception as e:
            logger.warning(f"Ошибка поиска в векторной БД: {e}")
            return []
        
        examples = []
        if results and results.get('ids') and results['ids']:
            for i, doc_id in enumerate(results['ids'][0]):
                doc_text = results['documents'][0][i] if results.get('documents') else ''
                meta = results['metadatas'][0][i] if results.get('metadatas') else {}
                
                examples.append({
                    'id': doc_id,
                    'text': doc_text,
                    'rating': meta.get('rating', 0),
                    'holiday': meta.get('holiday_title', ''),
                    'greeting_id': meta.get('greeting_id', 0)
                })
        
        logger.debug(f"Найдено {len(examples)} похожих примеров")
        return examples
    
    def get_statistics(self) -> Dict:
        """Возвращает статистику по накопленным примерам"""
        try:
            all_data = self.collection.get()
            if not all_data or not all_data.get('metadatas'):
                return {"total": 0, "avg_rating": 0}
            
            ratings = [m.get('rating', 0) for m in all_data['metadatas'] if m]
            return {
                "total": len(ratings),
                "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else 0,
            }
        except Exception as e:
            logger.warning(f"Ошибка получения статистики: {e}")
            return {"total": 0, "avg_rating": 0}


# Глобальный экземпляр
feedback_db = FeedbackVectorDB()