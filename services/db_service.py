import os
import ssl
import certifi
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()


class DatabaseManager:
    def __init__(self):
        mongo_url = os.getenv("MONGO_URL")
        db_name = os.getenv("DATABASE_NAME")

        self.client = AsyncIOMotorClient(
            mongo_url,
            serverSelectionTimeoutMS=5000,
            tlsCAFile=certifi.where()
        )
        self.db = self.client[db_name]

    async def check_connection(self):
        """Verifica si la base de datos está online para el indicador de React"""
        try:
            await self.client.admin.command('ping')
            return True
        except Exception as e:
            print(f"❌ Error de conexión a MongoDB: {e}")
            return False

    async def guardar_foto(self, nombre_evento: str, info_foto: dict):
        """Guarda la información de la foto procesada en la colección del evento"""
        collection = self.db[f"fotos_{nombre_evento}"]
        resultado = await collection.insert_one(info_foto)
        return str(resultado.inserted_id)

    async def buscar_fotos_por_rostros(self, nombre_evento: str, face_ids: list):
        """Busca URLs de fotos basándose en una lista de IDs de rostros encontrados por AWS"""
        collection = self.db[f"fotos_{nombre_evento}"]

        cursor = collection.find({"face_ids": {"$in": face_ids}})

        fotos_encontradas = []
        async for documento in cursor:
            fotos_encontradas.append({
                "id": str(documento["_id"]),
                "url": documento["url"],
                "nombre": documento.get("nombre_archivo", "Sin nombre")
            })
        return fotos_encontradas