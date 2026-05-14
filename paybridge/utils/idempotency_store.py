from __future__ import annotations

import base64
import json
import os
import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from ..core.config import logger


@dataclass
class CachedHttpResponse:
    status_code: int
    headers: Dict[str, str]
    content_b64: str
    url: str
    method: str

    @classmethod
    def from_response(cls, response: httpx.Response) -> "CachedHttpResponse":
        request = response.request
        url = str(request.url) if request and request.url else ""
        method = request.method if request else "GET"
        return cls(
            status_code=response.status_code,
            headers=dict(response.headers),
            content_b64=base64.b64encode(response.content).decode("ascii"),
            url=url,
            method=method,
        )

    def to_response(self) -> httpx.Response:
        request = httpx.Request(self.method, self.url or "https://localhost/")
        content = base64.b64decode(self.content_b64.encode("ascii"))
        return httpx.Response(
            status_code=self.status_code,
            headers=self.headers,
            content=content,
            request=request,
        )


@dataclass
class IdempotencyRecord:
    provider: str
    endpoint: str
    started_at: float
    expires_at: float
    status: str = "in_progress"
    response: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IdempotencyRecord":
        return cls(**data)


class IdempotencyStore(ABC):
    @abstractmethod
    def generate_key(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def start_request(self, key: str, provider_name: str, endpoint: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def record_response(self, key: str, response: httpx.Response) -> None:
        raise NotImplementedError

    @abstractmethod
    def record_error(self, key: str, error: Exception) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_cached_response(self, key: str) -> Optional[httpx.Response]:
        raise NotImplementedError

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def cleanup_expired(self) -> None:
        raise NotImplementedError


class InMemoryIdempotencyStore(IdempotencyStore):
    def __init__(self, ttl_seconds: int = 3600):
        self.ttl_seconds = ttl_seconds
        self._requests: Dict[str, IdempotencyRecord] = {}
        self._lock = threading.Lock()

    def generate_key(self) -> str:
        return str(uuid.uuid4())

    def start_request(self, key: str, provider_name: str, endpoint: str) -> bool:
        self.cleanup_expired()

        with self._lock:
            if key in self._requests:
                record = self._requests[key]
                logger.warning(
                    f"[{provider_name}] Duplicate request detected: {endpoint} "
                    f"(original started {time.time() - record.started_at:.1f}s ago)"
                )
                return False

            started_at = time.time()
            self._requests[key] = IdempotencyRecord(
                provider=provider_name,
                endpoint=endpoint,
                started_at=started_at,
                expires_at=started_at + self.ttl_seconds,
            )
            logger.debug(f"[{provider_name}] Tracking request {key[:8]}... to {endpoint}")
            return True

    def record_response(self, key: str, response: httpx.Response) -> None:
        with self._lock:
            if key not in self._requests:
                return
            record = self._requests[key]
            record.status = "success"
            record.response = _serialize_response_value(response)
            record.completed_at = time.time()
            logger.debug(f"Idempotency tracker: response recorded for {key[:8]}...")

    def record_error(self, key: str, error: Exception) -> None:
        with self._lock:
            if key not in self._requests:
                return
            record = self._requests[key]
            record.status = "error"
            record.error = str(error)
            record.completed_at = time.time()
            logger.debug(f"Idempotency tracker: error recorded for {key[:8]}...")

    def get_cached_response(self, key: str) -> Optional[httpx.Response]:
        self.cleanup_expired()

        with self._lock:
            record = self._requests.get(key)
            if not record or not record.response:
                return None
            logger.info(f"Returning cached response for idempotency key {key[:8]}...")
            return _response_from_payload(record.response)

    def cleanup_expired(self) -> None:
        now = time.time()
        with self._lock:
            expired_keys = [
                key for key, record in self._requests.items()
                if record.expires_at <= now
            ]
            for key in expired_keys:
                del self._requests[key]
                logger.debug(f"Idempotency tracker: cleaned up expired entry {key[:8]}...")

    def get_stats(self) -> Dict[str, Any]:
        self.cleanup_expired()
        with self._lock:
            return {
                "tracked_requests": len(self._requests),
                "entries": [
                    {
                        "key": key[:8] + "...",
                        "provider": record.provider,
                        "endpoint": record.endpoint,
                        "age_seconds": time.time() - record.started_at,
                        "status": record.status,
                    }
                    for key, record in self._requests.items()
                ],
            }


class FileIdempotencyStore(IdempotencyStore):
    def __init__(self, file_path: str, ttl_seconds: int = 3600):
        self.file_path = Path(file_path)
        self.ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self._write({})

    def generate_key(self) -> str:
        return str(uuid.uuid4())

    def start_request(self, key: str, provider_name: str, endpoint: str) -> bool:
        self.cleanup_expired()

        with self._lock:
            data = self._read()
            if key in data:
                record = IdempotencyRecord.from_dict(data[key])
                logger.warning(
                    f"[{provider_name}] Duplicate request detected: {endpoint} "
                    f"(original started {time.time() - record.started_at:.1f}s ago)"
                )
                return False

            started_at = time.time()
            data[key] = IdempotencyRecord(
                provider=provider_name,
                endpoint=endpoint,
                started_at=started_at,
                expires_at=started_at + self.ttl_seconds,
            ).to_dict()
            self._write(data)
            logger.debug(f"[{provider_name}] Tracking request {key[:8]}... to {endpoint}")
            return True

    def record_response(self, key: str, response: httpx.Response) -> None:
        with self._lock:
            data = self._read()
            if key not in data:
                return

            record = IdempotencyRecord.from_dict(data[key])
            record.status = "success"
            record.response = _serialize_response(response)
            record.completed_at = time.time()
            data[key] = record.to_dict()
            self._write(data)
            logger.debug(f"Idempotency tracker: response recorded for {key[:8]}...")

    def record_error(self, key: str, error: Exception) -> None:
        with self._lock:
            data = self._read()
            if key not in data:
                return

            record = IdempotencyRecord.from_dict(data[key])
            record.status = "error"
            record.error = str(error)
            record.completed_at = time.time()
            data[key] = record.to_dict()
            self._write(data)
            logger.debug(f"Idempotency tracker: error recorded for {key[:8]}...")

    def get_cached_response(self, key: str) -> Optional[httpx.Response]:
        self.cleanup_expired()

        with self._lock:
            data = self._read()
            record_data = data.get(key)
            if not record_data:
                return None

            record = IdempotencyRecord.from_dict(record_data)
            if not record.response:
                return None

            logger.info(f"Returning cached response for idempotency key {key[:8]}...")
            return _response_from_payload(record.response)

    def cleanup_expired(self) -> None:
        now = time.time()
        with self._lock:
            data = self._read()
            expired = [key for key, record in data.items() if IdempotencyRecord.from_dict(record).expires_at <= now]
            for key in expired:
                del data[key]
                logger.debug(f"Idempotency tracker: cleaned up expired entry {key[:8]}...")
            if expired:
                self._write(data)

    def get_stats(self) -> Dict[str, Any]:
        self.cleanup_expired()
        with self._lock:
            data = self._read()
            return {
                "tracked_requests": len(data),
                "entries": [
                    {
                        "key": key[:8] + "...",
                        "provider": record["provider"],
                        "endpoint": record["endpoint"],
                        "age_seconds": time.time() - record["started_at"],
                        "status": record.get("status", "in_progress"),
                    }
                    for key, record in data.items()
                ],
            }

    def _read(self) -> Dict[str, Dict[str, Any]]:
        if not self.file_path.exists():
            return {}
        with self.file_path.open("r", encoding="utf-8") as handle:
            try:
                return json.load(handle)
            except json.JSONDecodeError:
                return {}

    def _write(self, data: Dict[str, Dict[str, Any]]) -> None:
        temp_path = self.file_path.with_suffix(self.file_path.suffix + ".tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
        os.replace(temp_path, self.file_path)


def _serialize_response(response: httpx.Response) -> Dict[str, Any]:
    return _serialize_response_value(response)


def _serialize_response_value(response: Any) -> Dict[str, Any]:
    if isinstance(response, httpx.Response):
        return {
            "kind": "httpx",
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "content_b64": base64.b64encode(response.content).decode("ascii"),
            "url": str(response.request.url) if response.request else "",
            "method": response.request.method if response.request else "GET",
        }

    return {
        "kind": "raw",
        "value": response,
    }


def _response_from_payload(payload: Dict[str, Any]) -> httpx.Response:
    if payload.get("kind") == "raw":
        return payload.get("value")

    request = httpx.Request(payload.get("method", "GET"), payload.get("url") or "https://localhost/")
    content = base64.b64decode(payload.get("content_b64", "").encode("ascii"))
    return httpx.Response(
        status_code=int(payload.get("status_code", 200)),
        headers=payload.get("headers", {}),
        content=content,
        request=request,
    )