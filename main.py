import os
from fastapi import FastAPI, UploadFile, File
from services.aws_service import AmazonRekognitionManager
from fastapi.middleware.cors import CORSMiddleware
from services.db_service import DatabaseManager

app = FastAPI()
# 1. AJUSTE DE CORS PARA PRODUCCIÓN
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

# Instanciamos los managers
aws_manager = AmazonRekognitionManager()
db_manager = DatabaseManager()

@app.get("/")
def home():
    # Útil para que Render sepa que el servicio está vivo
    return {"status": "online", "message": "API de Reconocimiento Facial lista"}

# ... (Tus otros endpoints se mantienen igual, están bien estructurados) ...

@app.post("/crear-evento/{nombre_evento}")
async def endpoint_crear_coleccion(nombre_evento: str):
    resultado = aws_manager.crear_coleccion(nombre_evento)
    return resultado

@app.post("/procesar-foto-evento/{nombre_evento}")
async def procesar_foto(nombre_evento: str, file: UploadFile = File(...)):
    image_bytes = await file.read()
    file_path_s3 = f"{nombre_evento}/{file.filename}"
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
        id_db = await db_manager.guardar_foto(nombre_evento, datos_para_db)
        return {
            "status": "procesado",
            "caras_detectadas": len(face_ids),
            "url": url_foto,
            "mongo_id": id_db
        }
    return {"status": "error", "detalle": "No se detectaron caras o error en S3"}

@app.post("/buscar-mis-fotos/{nombre_evento}")
async def endpoint_buscar_fotos(nombre_evento: str, file: UploadFile = File(...)):
    selfie_bytes = await file.read()
    resultado_aws = aws_manager.buscar_por_selfie(nombre_evento, selfie_bytes)
    if "error" in resultado_aws:
        return {"error": resultado_aws["error"], "fotos": []}
    face_ids_encontrados = [match['face_id'] for match in resultado_aws.get('matches', [])]
    if not face_ids_encontrados:
        return {"mensaje": "No encontramos fotos tuyas", "fotos": []}
    fotos_finales = await db_manager.buscar_fotos_por_rostros(nombre_evento, face_ids_encontrados)
    return {
        "mensaje": f"¡Encontramos {len(fotos_finales)} fotos!",
        "fotos": fotos_finales
    }

@app.get("/check-db")
async def check_db():
    is_connected = await db_manager.check_connection()
    return {"status": "connected" if is_connected else "disconnected"}

# 2. PUERTO DINÁMICO PARA DESPLIEGUE
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)