import os
from dotenv import load_dotenv
import boto3
from botocore.client import Config

load_dotenv()

ACCOUNT_ID = os.environ["R2_ACCOUNT_ID"]
ACCESS_KEY = os.environ["R2_ACCESS_KEY_ID"]
SECRET_KEY = os.environ["R2_SECRET_ACCESS_KEY"]
BUCKET = os.environ["R2_BUCKET"]

s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    config=Config(signature_version="s3v4"),
    region_name="auto",
)

file_path = "certiliving.png"

with open(file_path, "rb") as f:
    s3.put_object(
        Bucket=BUCKET,
        Key="test/certiliving.png",
        Body=f,
        ContentType="image/png",
    )

print("Upload successful: test/certiliving.png")
