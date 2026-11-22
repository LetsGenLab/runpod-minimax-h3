"""Run the official worker with media-aware output handling."""

import mimetypes
import os
from pathlib import Path
from uuid import uuid4

import worker_comfyui


def collect_media_outputs(history, prompt_id):
    for output in history.get(prompt_id, {}).get("outputs", {}).values():
        files = list(output.get("images", []))
        for key in ("videos", "audio"):
            for entry in output.pop(key, []):
                if (
                    isinstance(entry, dict)
                    and entry.get("filename")
                    and entry.get("type") == "output"
                    and entry not in files
                ):
                    files.append(entry)
        if files:
            output["images"] = files
    return history


def upload_media(client, bucket, job_id, filename):
    key = f"{job_id}/{uuid4().hex}{Path(filename).suffix}"
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    client.upload_file(filename, bucket, key, ExtraArgs={"ContentType": content_type})
    return client.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=3600
    )


if __name__ == "__main__":
    get_history = worker_comfyui.get_history

    def get_media_history(prompt_id):
        return collect_media_outputs(get_history(prompt_id), prompt_id)

    worker_comfyui.get_history = get_media_history
    if os.environ.get("BUCKET_ENDPOINT_URL"):
        import boto3
        from botocore.config import Config

        bucket = os.environ["BUCKET_NAME"]
        client = boto3.client(
            "s3",
            endpoint_url=os.environ["BUCKET_ENDPOINT_URL"],
            aws_access_key_id=os.environ["BUCKET_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["BUCKET_SECRET_ACCESS_KEY"],
            region_name=os.environ.get("BUCKET_REGION", "us-east-1"),
            config=Config(signature_version="s3v4"),
        )

        def upload_result(job_id, filename):
            return upload_media(client, bucket, job_id, filename)

        worker_comfyui.rp_upload.upload_image = upload_result

    worker_comfyui.runpod.serverless.start({"handler": worker_comfyui.handler})
