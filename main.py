import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from services.aws_service import AmazonRekognitionManager
from fastapi.middleware.cors import CORSMiddleware
from services.db_service import DatabaseManager

app = FastAPI()

origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://face-rekognition-front.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

aws_manager = AmazonRekognitionManager()
db_manager = DatabaseManager()


@app.get("/")
def home():
    return {"status": "online", "message": "API lista"}


@app.post("/crear-evento/{nombre_evento}")
async def endpoint_crear_coleccion(nombre_evento: str):
    return aws_manager.crear_coleccion(nombre_evento)


@app.post("/procesar-foto-evento/{nombre_evento}")
async def procesar_foto(nombre_evento: str, file: UploadFile = File(...)):
    image_bytes = await file.read()
    # Guardamos en S3 dentro de una carpeta con el nombre del evento
    file_path_s3 = f"{nombre_evento}/{file.filename}"

    # Aseguramos que la colección exista en AWS
    aws_manager.crear_coleccion(nombre_evento)

    url_foto = aws_manager.subir_a_s3(image_bytes, file_path_s3)
    resultado_aws = aws_manager.indexar_cara(nombre_evento, image_bytes, file.filename)

    face_ids = [face['Face']['FaceId'] for face in resultado_aws.get('FaceRecords', [])]

    if url_foto and face_ids:
        datos_para_db = {
            "url": url_foto,
            "face_ids": face_ids,
            "evento": nombre_evento,
            "nombre_archivo": file.filename
        }
        # db_manager ya añade el prefijo 'fotos_' internamente
        id_db = await db_manager.guardar_foto(nombre_evento, datos_para_db)
        return {
            "status": "procesado",
            "caras_detectadas": len(face_ids),
            "url": url_foto,
            "mongo_id": id_db
        }
    return {"status": "error", "detalle": "No se detectaron rostros"}


@app.post("/buscar-mis-fotos/{nombre_evento}")
async def endpoint_buscar_fotos(nombre_evento: str, file: UploadFile = File(...)):
    selfie_bytes = await file.read()

    # Buscamos en la colección de AWS
    resultado_aws = aws_manager.buscar_por_selfie(nombre_evento, selfie_bytes)

    if "error" in resultado_aws:
        return {"error": resultado_aws["error"], "fotos": []}

    face_ids_encontrados = [match['face_id'] for match in resultado_aws.get('matches', [])]

    if not face_ids_encontrados:
        return {"mensaje": "No se encontraron coincidencias faciales.", "fotos": []}

    # Buscamos las URLs en MongoDB usando los FaceIds
    fotos_finales = await db_manager.buscar_fotos_por_rostros(nombre_evento, face_ids_encontrados)

    return {
        "mensaje": f"¡Encontramos {len(fotos_finales)} fotos!",
        "fotos": fotos_finales
    }


@app.get("/listar-eventos")
async def listar_eventos():
    colecciones = await db_manager.db.list_collection_names()
    # Limpiamos los nombres para el Front (quitamos el prefijo 'fotos_')
    eventos_limpios = [c.replace("fotos_", "") for c in colecciones if c.startswith("fotos_")]
    return {"eventos": eventos_limpios}


@app.get("/check-db")
async def check_db():
    is_connected = await db_manager.check_connection()
    return {"status": "connected" if is_connected else "disconnected"}


@app.delete("/eliminar-evento/{nombre_evento}")
async def eliminar_evento(nombre_evento: str):
    try:
        # 1. Borrar en Mongo
        await db_manager.db.drop_collection(f"fotos_{nombre_evento}")
        # 2. Borrar en AWS (Opcional, pero recomendado)
        try:
            aws_manager.rekognition.delete_collection(CollectionId=nombre_evento)
        except:
            pass
        return {"status": "success", "message": f"Evento {nombre_evento} eliminado"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)