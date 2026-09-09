from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from typing import IO, BinaryIO, Protocol, cast

from minio import Minio

from app.core.config import get_settings


@dataclass(frozen=True)
class StoredObject:
    object_key: str
    size_bytes: int
    etag: str


class ObjectStorage(Protocol):
    def upload(
        self,
        object_key: str,
        stream: IO[bytes],
        size_bytes: int,
        media_type: str,
    ) -> StoredObject: ...

    def remove(self, object_key: str) -> None: ...

    def stat(self, object_key: str) -> StoredObject: ...

    def presigned_download(self, object_key: str, filename: str) -> str: ...


class MinioObjectStorage:
    def __init__(self) -> None:
        settings = get_settings()
        self.bucket = settings.minio_bucket
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.download_client = Minio(
            settings.minio_public_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    def _ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def upload(
        self,
        object_key: str,
        stream: IO[bytes],
        size_bytes: int,
        media_type: str,
    ) -> StoredObject:
        self._ensure_bucket()
        stream.seek(0)
        result = self.client.put_object(
            self.bucket,
            object_key,
            cast(BinaryIO, stream),
            length=size_bytes,
            content_type=media_type,
        )
        return StoredObject(object_key=object_key, size_bytes=size_bytes, etag=result.etag or "")

    def remove(self, object_key: str) -> None:
        self.client.remove_object(self.bucket, object_key)

    def stat(self, object_key: str) -> StoredObject:
        result = self.client.stat_object(self.bucket, object_key)
        if result.size is None:
            raise RuntimeError(f"Object {object_key} has no size metadata")
        return StoredObject(
            object_key=object_key,
            size_bytes=result.size,
            etag=result.etag or "",
        )

    def presigned_download(self, object_key: str, filename: str) -> str:
        safe_filename = filename.replace('"', "_").replace("\r", "_").replace("\n", "_")
        return self.download_client.presigned_get_object(
            self.bucket,
            object_key,
            expires=timedelta(minutes=15),
            response_headers={
                "response-content-disposition": f'attachment; filename="{safe_filename}"'
            },
        )


@lru_cache
def get_object_storage() -> ObjectStorage:
    return MinioObjectStorage()
