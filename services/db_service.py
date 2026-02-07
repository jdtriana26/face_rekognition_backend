import os
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
        try:
            await self.client.admin.command('ping')
            return True
        except Exception as e:
            print(f"❌ Error de conexión a MongoDB: {e}")
            return False

    async def guardar_foto(self, nombre_evento: str, info_foto: dict):
        # Estandarizamos el nombre de la colección con prefijo
        nombre_coleccion = f"fotos_{nombre_evento}"
        collection = self.db[nombre_coleccion]
        resultado = await collection.insert_one(info_foto)
        return str(resultado.inserted_id)

    async def buscar_fotos_por_rostros(self, nombre_evento, face_ids_encontrados):
        try:
            # IMPORTANTE: Usamos el mismo prefijo que en guardar_foto
            nombre_coleccion = f"fotos_{nombre_evento}"
            coleccion = self.db[nombre_coleccion]

            print(f"🔍 Consultando MongoDB en: {nombre_coleccion}")

            # Buscamos cualquier documento donde al menos un face_id de la lista coincida
            cursor = coleccion.find({"face_ids": {"$in": face_ids_encontrados}})

            fotos = []
            async for doc in cursor:
                fotos.append({
                    "url": doc["url"],
                    "caras": len(doc.get("face_ids", [])),
                    "nombre": doc.get("nombre_archivo", "foto.jpg")
                })

            print(f"✅ Se encontraron {len(fotos)} coincidencias en Mongo")
            return fotos
        except Exception as e:
            print(f"❌ Error en Mongo: {e}")
            return []