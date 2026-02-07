import boto3
import os
from dotenv import load_dotenv

load_dotenv()

class AmazonRekognitionManager:
    def __init__(self):
        self.access_key = os.getenv('AWS_ACCESS_KEY_ID')
        self.secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        self.region = os.getenv('AWS_REGION')
        self.bucket_name = os.getenv('AWS_BUCKET_NAME')

        self.rekognition = boto3.client(
            'rekognition',
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region
        )

        self.s3 = boto3.client(
            's3',
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region
        )

    def subir_a_s3(self, file_bytes, file_name):
        try:
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=file_name,
                Body=file_bytes,
                ContentType='image/jpeg'
            )
            return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{file_name}"
        except Exception as e:
            print(f"Error S3: {e}")
            return None

    def crear_coleccion(self, collection_id: str):
        try:
            return self.rekognition.create_collection(CollectionId=collection_id)
        except self.rekognition.exceptions.ResourceAlreadyExistsException:
            return {"message": "Ya existe"}

    def indexar_cara(self, collection_id, image_bytes, external_id):
        try:
            response = self.rekognition.index_faces(
                CollectionId=collection_id,
                Image={'Bytes': image_bytes},
                ExternalImageId=external_id.replace("/", "_"),  # Rekognition no recibe slashes aquí
                DetectionAttributes=['ALL']
            )
            return response
        except Exception as e:
            print(f"❌ Error en AWS IndexFaces: {e}")
            return {}

    def buscar_por_selfie(self, collection_id: str, image_bytes: bytes):
        try:
            # Log para depuración: Verificamos que collection_id sea el correcto
            print(f"🔍 Buscando en la colección de AWS: {collection_id}")

            response = self.rekognition.search_faces_by_image(
                CollectionId=collection_id,
                Image={'Bytes': image_bytes},
                MaxFaces=20,  # Aumentamos a 20 por si hay muchas fotos anteriores
                FaceMatchThreshold=70  # Si no encuentra nada, prueba bajando a 60
            )

            matches = []
            for match in response.get('FaceMatches', []):
                matches.append({
                    "face_id": match['Face']['FaceId'],
                    "similarity": match['Similarity']
                })

            return {"matches": matches}
        except self.rekognition.exceptions.ResourceNotFoundException:
            print(f"❌ Error: La colección {collection_id} no existe en AWS.")
            return {"error": "El evento no tiene un índice de caras creado.", "matches": []}
        except Exception as e:
            print(f"❌ Error en Búsqueda AWS: {e}")
            return {"error": str(e), "matches": []}