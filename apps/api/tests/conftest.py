import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import IO
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_database_session
from app.main import app
from app.services.dispatch import get_job_dispatcher
from app.services.storage import ObjectStorage, StoredObject, get_object_storage


class FakeStorage(ObjectStorage):
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def upload(
        self, object_key: str, stream: IO[bytes], size_bytes: int, media_type: str
    ) -> StoredObject:
        del media_type
        content = stream.read()
        assert len(content) == size_bytes
        self.objects[object_key] = content
        return StoredObject(object_key=object_key, size_bytes=size_bytes, etag="fake-etag")

    def remove(self, object_key: str) -> None:
        self.objects.pop(object_key, None)

    def stat(self, object_key: str) -> StoredObject:
        content = self.objects[object_key]
        return StoredObject(object_key=object_key, size_bytes=len(content), etag="fake-etag")

    def presigned_download(self, object_key: str, filename: str) -> str:
        assert object_key in self.objects
        return f"https://storage.invalid/{object_key}?filename={filename}"

    def download_to_file(self, object_key: str, destination: Path) -> None:
        destination.write_bytes(self.objects[object_key])


class FakeDispatcher:
    def __init__(self) -> None:
        self.dispatched: list[tuple[UUID, str]] = []
        self.fail = False

    def dispatch(self, job_id: UUID, job_type: str) -> None:
        if self.fail:
            raise RuntimeError("broker unavailable")
        self.dispatched.append((job_id, job_type))

    @property
    def job_ids(self) -> list[UUID]:
        return [job_id for job_id, _job_type in self.dispatched]


@pytest.fixture
def m1_environment(
    tmp_path: Path,
) -> Iterator[tuple[TestClient, FakeStorage, FakeDispatcher, async_sessionmaker]]:
    database_path = tmp_path / "m1-test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def prepare() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(prepare())
    storage = FakeStorage()
    dispatcher = FakeDispatcher()

    async def override_session():  # type: ignore[no-untyped-def]
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_database_session] = override_session
    app.dependency_overrides[get_object_storage] = lambda: storage
    app.dependency_overrides[get_job_dispatcher] = lambda: dispatcher

    with TestClient(app) as client:
        yield client, storage, dispatcher, session_factory

    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())
