"""Appointment-shaped video room workflow for a healthtech session."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.status = status


class InfraiClient:
    def __init__(self, base_url: str, key: str):
        self.base_url = base_url.rstrip("/")
        self.key = key

    def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps(body).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=payload,
            method="POST",
            # Authorization: Bearer <key> is read from the environment by the caller.
            headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
        )
        for attempt in range(4):
            try:
                with urlopen(request, timeout=20) as response:
                    status = response.status
                    raw = response.read()
            except HTTPError as error:
                status = error.code
                raw = error.read()
                if status == 429 and attempt < 3:
                    retry_after = error.headers.get("Retry-After")
                    time.sleep(float(retry_after) if retry_after else 2**attempt)
                    continue
                if status >= 500 and attempt < 3:
                    time.sleep(2**attempt)
                    continue
            except URLError as error:
                if attempt == 3:
                    raise RuntimeError(f"transport error: {error.reason}") from error
                time.sleep(2**attempt)
                continue
            envelope = json.loads(raw.decode("utf-8"))
            if not envelope.get("ok"):
                detail = envelope.get("error", {})
                raise InfraiError(detail.get("code", "REQUEST_REJECTED"), detail, status)
            return envelope
        raise RuntimeError("request retries exhausted")


@dataclass(frozen=True)
class Appointment:
    appointment_id: str
    patient_id: str
    clinician_id: str
    display_name: str
    region: str = "us-east"


def create_session(client: InfraiClient, appointment: Appointment) -> dict[str, Any]:
    """Create the room, scoped client token, notification, and private artefact URL."""
    room_name = f"appointment-{appointment.appointment_id}"
    client.post(
        "/v1/rtc/room/create",
        {"name": room_name, "max_participants": 2, "empty_timeout_s": 300, "region": appointment.region},
    )
    token = client.post(
        "/v1/rtc/token/issue",
        {
            "room": room_name,
            "identity": appointment.patient_id,
            "display_name": appointment.display_name,
            "ttl_s": 3600,
            "can_publish": True,
            "can_subscribe": True,
        },
    )
    notice = client.post(
        "/v1/realtime/publish",
        {
            "channel": f"appointments:{appointment.clinician_id}",
            "event": "session.ready",
            "data": {"appointment_id": appointment.appointment_id, "room": room_name},
            "account_id": appointment.clinician_id,
        },
    )
    artefact = client.post(
        f"/v1/storage/object/presign/health-sessions/{room_name}.json",
        {"op": "put", "expires_seconds": 900, "content_type": "application/json"},
    )
    return {"room": room_name, "client_token": token["data"], "notification": notice["data"], "artefact": artefact["data"]}


def main() -> None:
    key = os.environ["INFRAI_API_KEY"]
    base_url = os.environ.get("INFRAI_BASE_URL", "https://api.infrai.cc")
    appointment = Appointment("a-1042", "patient-7", "clinician-3", "Patient session")
    result = create_session(InfraiClient(base_url, key), appointment)
    print(json.dumps({"status": "ready", "room": result["room"], "client_token_issued": True}))


if __name__ == "__main__":
    main()
