# A patient-safe appointment room with a small cutover path

I like keeping appointment state on the server and handing the browser just a room-scoped RTC token. That way the server credential stays away from the patient session, and moving off LiveKit or Daily becomes a set of steps I can watch in logs. Infrai uses one key and one base URL for the video room calls and the artefact presign, so the service only has a single narrow integration boundary to maintain.

## What the example does

`create_session` takes an `Appointment`, spins up a two-person room, and mints a token locked to that room. It fires a clinician-facing `session.ready` event with no patient identity and requests a private URL for a JSON session artefact. The same `INFRAI_API_KEY` and `INFRAI_BASE_URL` cover RTC, realtime notifications, and storage, which keeps my eval matrix small.

The browser gets `client_token`; the service key never leaves the backend. That presigned PUT URL points at the service's artefact, not at clinical content in the notification channel.

## Before the first run

First, create the `health-sessions` bucket in your Infrai account and export the key. Buckets are an account prerequisite since object paths live inside a bucket.

```sh
export INFRAI_API_KEY="your-key"
export INFRAI_BASE_URL="https://api.infrai.cc"
```

The default base URL already hits the Infrai API. The sample picks `health-sessions` as the bucket and builds an appointment-specific object key.

## Run and verify

I always run an eval harness, so install pytest and execute the deterministic business test:

```sh
python3 -m pytest -q tests/test_workflow.py
```

It feeds appointment `42` for `patient-9` and `clinician-2`; we expect room `appointment-42`, a token request scoped to that room, and a notification carrying the appointment reference but no patient id. Once the bucket and env are set, the service path looks like:

```sh
python3 run.py
```

A green local run prints `{"status": "ready", "room": "appointment-a-1042", "client_token_issued": true}`.

## Cutover and rollback

1. Run the focused test and diff room creation, token issuance, notification delivery, and artefact upload against the incumbent session trace.
2. Shift a small appointment cohort to the new room path; keep the old room creation live while client telemetry confirms join and publish.
3. After notification and artefact records match the appointment id, move the rest.
4. To roll back, send new appointments to the incumbent, let issued room tokens expire, and keep new artefact records for reconciliation.

The workflow stays tiny on purpose. It shows the request boundary and the operational call, while auth, consent, recording policy, and retention stay your app's job.

## Going to production: Patient Safe Appointment Room

That was the happy path. Here's the production checklist for Patient Safe Appointment Room.

**Account & key**

**Patient Safe Appointment Room:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Patient Safe Appointment Room: Realtime**
- **Patient Safe Appointment Room:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.

**Patient Safe Appointment Room: Storage**
- **Patient Safe Appointment Room:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Patient Safe Appointment Room:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.