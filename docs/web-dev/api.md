# REST API – version 1

Base path: `/api/v1`. All responses are JSON. The API uses the same login session as the
web pages: log in through `/login` first (the session cookie is `HttpOnly`, `SameSite=Lax`,
and `Secure` in production).

## Authentication and CSRF

| Situation | Response |
|---|---|
| Not logged in | `401 {"error": "Login required."}` |
| Logged in, but the action needs the owner role | `403 {"error": "Only the owner can do this."}` |
| Write request (`POST`, `PUT`, `DELETE`) without a valid `X-CSRF-Token` header | `400 {"error": "Missing or invalid CSRF token."}` |

Get the CSRF token for the current session:

```
GET /api/v1/session
200 {"username": "manager", "role": "manager", "csrf_token": "..."}
```

Send it with every write request: `X-CSRF-Token: <token>`.

## Errors

| Code | Meaning | Body |
|---|---|---|
| 400 | Body is not a JSON object, or CSRF token missing | `{"error": "..."}` |
| 404 | Order or stage does not exist | `{"error": "..."}` |
| 409 | Conflict: duplicate order code, stage already started, stage not running | `{"error": "..."}` or `{"errors": {...}}` |
| 422 | Validation failed | `{"errors": {"field": "message", ...}}` (messages in Uzbek, as shown to the manager) |

## Endpoints

### List orders

```
GET /api/v1/orders?status=open|completed
200 {"orders": [ {order}, ... ]}
```

`status` is optional; without it all orders are returned, newest first.

### Create an order

```
POST /api/v1/orders
Content-Type: application/json
X-CSRF-Token: <token>

{
  "order_code": "118",
  "box_type": "OFFSET",            // PLAIN | STENCIL | OFFSET | MICRO
  "quantity": 1500,
  "received_at": "2026-11-25T09:30",
  "material_in_stock": false,
  "material_received_at": null,     // optional, only when material was not in stock
  "finishing": "laminate",          // none | laminate | lacquer (OFFSET and MICRO only)
  "promised_date": "2026-12-01"     // optional
}

201 Created
Location: /api/v1/orders/42
{order with stages}
```

### Read one order

```
GET /api/v1/orders/<id>
200 {order with stages}
```

### Update an order

```
PUT /api/v1/orders/<id>
```

Same body as create. Once any stage has been recorded, `box_type` and `finishing` cannot
change (the route depends on them); the stored values are kept. `200 {order with stages}`.

### Delete an order (owner only)

```
DELETE /api/v1/orders/<id>
204 No Content
```

Deletes the order and all its stage records.

### Start a stage

```
POST /api/v1/orders/<id>/stages/<stage_id>/start
{"started_at": "2026-11-25T10:00"}      // optional, default: now

201 {order with stages}
```

The machine is filled in automatically when only one machine performs the stage.
A stage can be started only once per order (`409` otherwise).

### Finish a stage

```
POST /api/v1/orders/<id>/stages/<stage_id>/finish
{"boxes_completed": 1500, "boxes_defective": 12, "operators": 2,
 "finished_at": "2026-11-25T12:30"}     // finished_at optional, default: now

200 {order with stages}
```

`boxes_completed` cannot exceed the order quantity. When the last stage of the route is
finished, the order is completed automatically (`status: "completed"`).

## Order object

```json
{
  "id": 42,
  "order_code": "118",
  "box_type": "OFFSET",
  "quantity": 1500,
  "finishing": "laminate",
  "material_in_stock": false,
  "material_received_at": "2026-11-26T11:00",
  "received_at": "2026-11-25T09:30",
  "promised_date": "2026-12-01",
  "completed_at": null,
  "status": "open",
  "entered_by": "manager",
  "url": "/api/v1/orders/42",
  "stages": [
    {"stage_id": 2, "code": "PAPERCUT", "name": "Qogʻoz kesish", "machine": "M02",
     "started_at": "2026-11-26T11:30", "finished_at": "2026-11-26T12:10",
     "boxes_completed": 1500, "boxes_defective": 0, "operators": 1, "status": "finished"}
  ]
}
```

Times are in workshop time (Asia/Tashkent), ISO 8601 without timezone.

## Example with curl

```bash
# log in and keep the session cookie
curl -c cookies.txt -d "username=manager&password=..." https://<app>.onrender.com/login
TOKEN=$(curl -s -b cookies.txt https://<app>.onrender.com/api/v1/session | python -c "import sys, json; print(json.load(sys.stdin)['csrf_token'])")

curl -b cookies.txt https://<app>.onrender.com/api/v1/orders?status=open
```

(With CSRF enabled, the login form itself also needs the token from the login page; the
easiest way to try the API is in the browser developer tools while logged in.)
