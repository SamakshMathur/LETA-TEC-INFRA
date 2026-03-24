import boto3
import os
import logging
from app.config import S3_BUCKET_NAME

logger = logging.getLogger(__name__)

def sync_from_s3():
    """Download data from S3 if not present locally."""
    s3 = boto3.client("s3")
    
    # We want to sync: RAG_INFORMATION_DATABASE, data, and vectordb
    folders_to_sync = ["RAG_INFORMATION_DATABASE", "data", "vectordb"]
    
    try:
        logger.info(f"Checking S3 bucket: {S3_BUCKET_NAME}")
        
        # List objects in the bucket
        paginator = s3.get_paginator('list_objects_v2')
        for result in paginator.paginate(Bucket=S3_BUCKET_NAME):
            if "Contents" not in result:
                logger.warning(f"S3 bucket {S3_BUCKET_NAME} is empty.")
                return

            for obj in result["Contents"]:
                key = obj["Key"]
                
                # Create local directory structure
                local_path = os.path.join(os.getcwd(), key)
                
                # If key ends with '/', it's a directory
                if key.endswith('/'):
                    os.makedirs(local_path, exist_ok=True)
                    continue
                
                # Ensure directory exists for the file
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                
                # Download if file doesn't exist
                if not os.path.exists(local_path):
                    logger.info(f"Downloading {key} from S3...")
                    s3.download_file(S3_BUCKET_NAME, key, local_path)
                else:
                    logger.debug(f"File {key} already exists, skipping.")
                    
        logger.info("S3 Sync Complete.")
        
    except Exception as e:
        logger.error(f"S3 Sync Error: {e}")
        # In production, you might want to raise this if data is critical
