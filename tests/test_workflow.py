from src.healthtech_service import Appointment, create_session


class RecordingClient:
    def __init__(self):
        self.calls = []

    def post(self, path, body):
        self.calls.append((path, body))
        return {"data": {"path": path}}


def test_session_uses_scoped_room_and_patient_safe_notice():
    client = RecordingClient()
    result = create_session(client, Appointment("42", "patient-9", "clinician-2", "Private visit"))

    assert result["room"] == "appointment-42"
    assert client.calls[1][1]["room"] == "appointment-42"
    assert client.calls[1][1]["identity"] == "patient-9"
    assert client.calls[2][1]["event"] == "session.ready"
    assert "patient-9" not in client.calls[2][1]["data"]
    assert client.calls[3][0].endswith("appointment-42.json")
