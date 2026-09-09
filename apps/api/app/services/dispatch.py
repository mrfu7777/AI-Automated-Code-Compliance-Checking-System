from typing import Protocol
from uuid import UUID


class JobDispatcher(Protocol):
    def dispatch_file_processing(self, job_id: UUID) -> None: ...


class CeleryJobDispatcher:
    def dispatch_file_processing(self, job_id: UUID) -> None:
        from app.tasks.file_processing import process_file_version

        process_file_version.delay(str(job_id))


def get_job_dispatcher() -> JobDispatcher:
    return CeleryJobDispatcher()
