import boto3
from botocore.client import Config
import base64
from typing import Dict, Optional
from app.core.config import settings


class S3Service:
    """Service for interacting with AWS S3 for activity flashcards."""
    
    def __init__(self):
        self._client = None
    
    @property
    def client(self):
        """Lazy initialization of S3 client."""
        if self._client is None and self._is_configured():
            self._client = boto3.client(
                "s3",
                region_name=settings.AWS_REGION,
                endpoint_url=f"https://s3.{settings.AWS_REGION}.amazonaws.com",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                config=Config(signature_version="s3v4")
            )
        return self._client
    
    def _is_configured(self) -> bool:
        """Check if AWS S3 is properly configured."""
        return all([
            settings.AWS_S3_BUCKET,
            settings.AWS_REGION,
            settings.AWS_ACCESS_KEY_ID,
            settings.AWS_SECRET_ACCESS_KEY
        ])
    
    def read_bytes_from_s3(self, key: str) -> bytes:
        """Read raw bytes from S3."""
        if not self.client:
            return b""
        obj = self.client.get_object(Bucket=settings.AWS_S3_BUCKET, Key=key)
        return obj["Body"].read()
    
    def fetch_flashcards(self, activity_id: str) -> Dict[str, str]:
        """
        Fetch flashcards from S3 for a given activity.
        
        Returns a dictionary mapping step names to base64 encoded images:
        {
            "step1": "base64String...",
            "step2": "base64String..."
        }
        """
        if not self.client or not settings.AWS_S3_BUCKET:
            return {}
        
        prefix = f"master/selected_activities/{activity_id}/flashcards/"
        
        try:
            response = self.client.list_objects_v2(
                Bucket=settings.AWS_S3_BUCKET, 
                Prefix=prefix
            )
        except Exception:
            return {}
        
        flashcards = {}
        
        if "Contents" not in response:
            return flashcards
        
        for obj in response["Contents"]:
            key = obj["Key"]
            if key.endswith((".png", ".jpg", ".jpeg")):
                try:
                    file_bytes = self.read_bytes_from_s3(key)
                    step_name = key.split("/")[-1].split(".")[0]
                    flashcards[step_name] = base64.b64encode(file_bytes).decode("utf-8")
                except Exception:
                    continue
        
        return flashcards

    def generate_presigned_url(self, key: str, expiration: int = 3600) -> Optional[str]:
        """Generate a presigned URL for an S3 object."""
        if not self.client or not settings.AWS_S3_BUCKET:
            return None
            
        try:
            return self.client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': settings.AWS_S3_BUCKET,
                    'Key': key
                },
                ExpiresIn=expiration
            )
        except Exception:
            return None


# Singleton instance
s3_service = S3Service()
