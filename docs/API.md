# BigTime Server API Documentation

Complete REST API reference for the BigTime Server.

**Base URL**: `http://localhost:5000`
**Version**: 1.0
**Authentication**: API Key (header: `X-API-Key`)

---

## 📋 Table of Contents

1. [Authentication](#authentication)
2. [Health & Info](#health--info)
3. [Time Endpoints](#time-endpoints)
4. [Employee Endpoints](#employee-endpoints)
5. [Time Log Endpoints](#time-log-endpoints)
6. [Sync Endpoints](#sync-endpoints)
7. [Error Responses](#error-responses)
8. [Data Models](#data-models)

---

## 🔐 Authentication

All API requests (except `/health` and `/api/v1/info`) require an API key.

### API Key Header

```http
X-API-Key: your-api-key-here
```

### Obtaining an API Key

API keys are generated via the server GUI:

1. Open server tray application
2. Right-click → "Server Settings"
3. Navigate to "API Keys" tab
4. Click "Generate New Key"
5. Enter device ID (e.g., `client-001`)
6. Copy the generated key

### Example Request

```bash
curl -H "X-API-Key: bt-abc123def456" http://localhost:5000/api/v1/employees
```

---

## 🏥 Health & Info

### GET /health

Check server health status (no authentication required).

**Request**:

```http
GET /health HTTP/1.1
Host: localhost:5000
```

**Response** (200 OK):

```json
{
  "status": "ok",
  "timestamp": "2025-10-14T10:30:00Z"
}
```

---

### GET /api/v1/info

Get server information (no authentication required).

**Request**:

```http
GET /api/v1/info HTTP/1.1
Host: localhost:5000
```

**Response** (200 OK):

```json
{
  "company_name": "SCR LLC",
  "server_version": "2.0",
  "api_version": "1.0",
  "timezone": "America/New_York",
  "features": {
    "time_sync": true,
    "ntp_available": true,
    "multi_client": true
  }
}
```

---

## ⏰ Time Endpoints

### GET /api/v1/time

Get current server time with timezone.

**Request**:

```http
GET /api/v1/time HTTP/1.1
Host: localhost:5000
X-API-Key: bt-abc123def456
```

**Response** (200 OK):

```json
{
  "server_time": "2025-10-14T10:30:45.123456",
  "timezone": "America/New_York",
  "utc_offset": "-04:00",
  "ntp_synced": true,
  "last_ntp_sync": "2025-10-14T10:25:00Z"
}
```

---

### POST /api/v1/time/sync

Trigger NTP time synchronization.

**Request**:

```http
POST /api/v1/time/sync HTTP/1.1
Host: localhost:5000
X-API-Key: bt-abc123def456
Content-Type: application/json

{
  "server": "pool.ntp.org"
}
```

**Parameters**:

- `server` (optional): NTP server address (default: `pool.ntp.org`)

**Response** (200 OK):

```json
{
  "status": "success",
  "synced_time": "2025-10-14T10:30:45.123456",
  "offset_ms": 12.5,
  "ntp_server": "pool.ntp.org"
}
```

**Response** (500 Internal Server Error):

```json
{
  "error": "NTP sync failed: timeout"
}
```

---

## 👥 Employee Endpoints

### GET /api/v1/employees

Get all employees or filter by criteria.

**Request**:

```http
GET /api/v1/employees HTTP/1.1
Host: localhost:5000
X-API-Key: bt-abc123def456
```

**Query Parameters**:

- `active_only` (boolean): Only return active employees (default: `false`)
- `department` (string): Filter by department
- `badge` (string): Get specific employee by badge

**Response** (200 OK):

```json
{
  "employees": [
    {
      "id": 1,
      "name": "John Doe",
      "badge": "EMP001",
      "phone_number": "5551234567",
      "department": "Engineering",
      "date_of_birth": "1990-01-15",
      "hire_date": "2020-03-01",
      "deactivated": false,
      "period": "hourly",
      "rate": 25.50,
      "created_at": "2020-03-01T09:00:00",
      "updated_at": "2025-10-14T10:30:00"
    }
  ],
  "count": 1
}
```

---

### POST /api/v1/employees

Create a new employee.

**Request**:

```http
POST /api/v1/employees HTTP/1.1
Host: localhost:5000
X-API-Key: bt-abc123def456
Content-Type: application/json

{
  "name": "Jane Smith",
  "badge": "EMP002",
  "phone_number": "5559876543",
  "pin": "1234",
  "department": "Sales",
  "date_of_birth": "1992-05-20",
  "hire_date": "2025-10-01",
  "period": "hourly",
  "rate": 22.00
}
```

**Required Fields**:

- `name`: Employee full name
- `badge`: Unique badge identifier

**Optional Fields**:

- `phone_number`: Contact phone
- `pin`: Security PIN (4-6 digits)
- `department`: Department name
- `date_of_birth`: Birth date (YYYY-MM-DD)
- `hire_date`: Hire date (YYYY-MM-DD)
- `ssn`: Social Security Number (stored as integer)
- `period`: Pay period type (`hourly` or `salary`)
- `rate`: Pay rate (hourly or annual)

**Response** (201 Created):

```json
{
  "status": "success",
  "employee": {
    "id": 2,
    "name": "Jane Smith",
    "badge": "EMP002",
    "phone_number": "5559876543",
    "department": "Sales",
    "date_of_birth": "1992-05-20",
    "hire_date": "2025-10-01",
    "deactivated": false,
    "period": "hourly",
    "rate": 22.00,
    "created_at": "2025-10-14T10:35:00",
    "updated_at": "2025-10-14T10:35:00"
  }
}
```

**Response** (400 Bad Request):

```json
{
  "error": "Badge 'EMP002' already exists"
}
```

---

### PUT /api/v1/employees/{badge}

Update an existing employee.

**Request**:

```http
PUT /api/v1/employees/EMP002 HTTP/1.1
Host: localhost:5000
X-API-Key: bt-abc123def456
Content-Type: application/json

{
  "department": "Management",
  "rate": 28.00
}
```

**Parameters**:

- Any employee fields (except `id`, `badge`, `created_at`)

**Response** (200 OK):

```json
{
  "status": "success",
  "employee": {
    "id": 2,
    "name": "Jane Smith",
    "badge": "EMP002",
    "department": "Management",
    "rate": 28.00,
    "updated_at": "2025-10-14T10:40:00"
  }
}
```

**Response** (404 Not Found):

```json
{
  "error": "Employee not found: EMP002"
}
```

---

### DELETE /api/v1/employees/{badge}

Deactivate an employee (soft delete).

**Request**:

```http
DELETE /api/v1/employees/EMP002 HTTP/1.1
Host: localhost:5000
X-API-Key: bt-abc123def456
```

**Response** (200 OK):

```json
{
  "status": "success",
  "message": "Employee EMP002 deactivated"
}
```

**Response** (404 Not Found):

```json
{
  "error": "Employee not found: EMP002"
}
```

---

## 📝 Time Log Endpoints

### GET /api/v1/logs

Get time logs with filtering.

**Request**:

```http
GET /api/v1/logs?badge=EMP001&start_date=2025-10-01&end_date=2025-10-14 HTTP/1.1
Host: localhost:5000
X-API-Key: bt-abc123def456
```

**Query Parameters**:

- `badge` (string): Filter by employee badge
- `start_date` (string): Start date (YYYY-MM-DD)
- `end_date` (string): End date (YYYY-MM-DD)
- `log_type` (string): Filter by type (`clock_in`, `clock_out`, `meal_start`, `meal_end`)

**Response** (200 OK):

```json
{
  "logs": [
    {
      "id": 1,
      "badge": "EMP001",
      "log_type": "clock_in",
      "timestamp": "2025-10-14T08:00:00",
      "notes": "",
      "created_at": "2025-10-14T08:00:00",
      "updated_at": "2025-10-14T08:00:00",
      "synced": true
    },
    {
      "id": 2,
      "badge": "EMP001",
      "log_type": "clock_out",
      "timestamp": "2025-10-14T17:00:00",
      "notes": "",
      "created_at": "2025-10-14T17:00:00",
      "updated_at": "2025-10-14T17:00:00",
      "synced": true
    }
  ],
  "count": 2
}
```

---

### POST /api/v1/logs

Create a new time log entry.

**Request**:

```http
POST /api/v1/logs HTTP/1.1
Host: localhost:5000
X-API-Key: bt-abc123def456
Content-Type: application/json

{
  "badge": "EMP001",
  "log_type": "clock_in",
  "timestamp": "2025-10-14T08:00:00",
  "notes": "Regular shift"
}
```

**Required Fields**:

- `badge`: Employee badge
- `log_type`: Type of log (`clock_in`, `clock_out`, `meal_start`, `meal_end`)
- `timestamp`: Time of event (ISO format)

**Optional Fields**:

- `notes`: Additional notes

**Response** (201 Created):

```json
{
  "status": "success",
  "log": {
    "id": 3,
    "badge": "EMP001",
    "log_type": "clock_in",
    "timestamp": "2025-10-14T08:00:00",
    "notes": "Regular shift",
    "created_at": "2025-10-14T08:00:15",
    "updated_at": "2025-10-14T08:00:15",
    "synced": true
  }
}
```

**Response** (400 Bad Request):

```json
{
  "error": "Employee not found: EMP999"
}
```

---

### PUT /api/v1/logs/{log_id}

Update an existing time log.

**Request**:

```http
PUT /api/v1/logs/3 HTTP/1.1
Host: localhost:5000
X-API-Key: bt-abc123def456
Content-Type: application/json

{
  "timestamp": "2025-10-14T08:05:00",
  "notes": "Adjusted time - late arrival"
}
```

**Parameters**:

- `timestamp` (optional): Update timestamp
- `notes` (optional): Update notes
- `log_type` (optional): Update type

**Response** (200 OK):

```json
{
  "status": "success",
  "log": {
    "id": 3,
    "badge": "EMP001",
    "log_type": "clock_in",
    "timestamp": "2025-10-14T08:05:00",
    "notes": "Adjusted time - late arrival",
    "updated_at": "2025-10-14T10:30:00"
  }
}
```

---

### DELETE /api/v1/logs/{log_id}

Delete a time log entry.

**Request**:

```http
DELETE /api/v1/logs/3 HTTP/1.1
Host: localhost:5000
X-API-Key: bt-abc123def456
```

**Response** (200 OK):

```json
{
  "status": "success",
  "message": "Log 3 deleted"
}
```

**Response** (404 Not Found):

```json
{
  "error": "Log not found: 999"
}
```

---

## 🔄 Sync Endpoints

### GET /api/v1/sync/state

Get current sync state for a device.

**Request**:

```http
GET /api/v1/sync/state?device_id=client-001 HTTP/1.1
Host: localhost:5000
X-API-Key: bt-abc123def456
```

**Response** (200 OK):

```json
{
  "device_id": "client-001",
  "last_sync": "2025-10-14T10:30:00",
  "sync_status": "success",
  "pending_changes": 0
}
```

---

### POST /api/v1/sync/push

Push local changes to server.

**Request**:

```http
POST /api/v1/sync/push HTTP/1.1
Host: localhost:5000
X-API-Key: bt-abc123def456
Content-Type: application/json

{
  "device_id": "client-001",
  "changes": [
    {
      "type": "log",
      "action": "create",
      "data": {
        "badge": "EMP001",
        "log_type": "clock_in",
        "timestamp": "2025-10-14T08:00:00"
      }
    }
  ]
}
```

**Response** (200 OK):

```json
{
  "status": "success",
  "processed": 1,
  "conflicts": 0,
  "sync_timestamp": "2025-10-14T10:30:00"
}
```

---

### GET /api/v1/sync/pull

Pull server changes since last sync.

**Request**:

```http
GET /api/v1/sync/pull?device_id=client-001&since=2025-10-14T10:00:00 HTTP/1.1
Host: localhost:5000
X-API-Key: bt-abc123def456
```

**Query Parameters**:

- `device_id`: Client device identifier
- `since`: Timestamp of last sync (ISO format)

**Response** (200 OK):

```json
{
  "changes": [
    {
      "type": "employee",
      "action": "update",
      "data": {
        "badge": "EMP002",
        "department": "Management",
        "updated_at": "2025-10-14T10:15:00"
      }
    }
  ],
  "count": 1,
  "sync_timestamp": "2025-10-14T10:30:00"
}
```

---

## ❌ Error Responses

### Standard Error Format

All errors follow this format:

```json
{
  "error": "Error message here",
  "details": "Additional details (optional)",
  "code": "ERROR_CODE (optional)"
}
```

### HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request successful |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid request data |
| 401 | Unauthorized | Invalid or missing API key |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Duplicate resource (e.g., badge exists) |
| 500 | Internal Server Error | Server error |

### Common Error Examples

**401 Unauthorized**:

```json
{
  "error": "Invalid API key"
}
```

**400 Bad Request**:

```json
{
  "error": "Missing required field: badge"
}
```

**409 Conflict**:

```json
{
  "error": "Badge 'EMP001' already exists"
}
```

**500 Internal Server Error**:

```json
{
  "error": "Database error",
  "details": "UNIQUE constraint failed: employees.badge"
}
```

---

## 📊 Data Models

### Employee

```typescript
{
  id: number,                  // Auto-generated
  name: string,                // Required
  badge: string,               // Required, unique
  phone_number?: string,       // Optional
  pin?: string,                // Optional (4-6 digits)
  department?: string,         // Optional
  date_of_birth?: string,      // Optional (YYYY-MM-DD)
  hire_date?: string,          // Optional (YYYY-MM-DD)
  deactivated: boolean,        // Default: false
  ssn?: number,                // Optional
  period: 'hourly' | 'salary', // Default: 'hourly'
  rate: number,                // Default: 0.0
  created_at: string,          // Auto-generated (ISO timestamp)
  updated_at: string           // Auto-updated (ISO timestamp)
}
```

### Time Log

```typescript
{
  id: number,                         // Auto-generated
  badge: string,                      // Required
  log_type: 'clock_in' | 'clock_out' | 'meal_start' | 'meal_end',
  timestamp: string,                  // Required (ISO timestamp)
  notes?: string,                     // Optional
  created_at: string,                 // Auto-generated
  updated_at: string,                 // Auto-updated
  synced: boolean                     // Sync status
}
```

### Sync State

```typescript
{
  device_id: string,           // Unique device identifier
  last_sync: string,           // ISO timestamp
  sync_status: 'success' | 'pending' | 'error',
  pending_changes: number      // Count of unsynced changes
}
```

---

## 🔍 Examples

### Complete Workflow Example

```bash
# 1. Check server health
curl http://localhost:5000/health

# 2. Get server info
curl http://localhost:5000/api/v1/info

# 3. Get current time
curl -H "X-API-Key: bt-abc123" http://localhost:5000/api/v1/time

# 4. Create employee
curl -X POST \
  -H "X-API-Key: bt-abc123" \
  -H "Content-Type: application/json" \
  -d '{"name":"John Doe","badge":"EMP001","rate":25.00}' \
  http://localhost:5000/api/v1/employees

# 5. Clock in
curl -X POST \
  -H "X-API-Key: bt-abc123" \
  -H "Content-Type: application/json" \
  -d '{"badge":"EMP001","log_type":"clock_in","timestamp":"2025-10-14T08:00:00"}' \
  http://localhost:5000/api/v1/logs

# 6. Clock out
curl -X POST \
  -H "X-API-Key: bt-abc123" \
  -H "Content-Type: application/json" \
  -d '{"badge":"EMP001","log_type":"clock_out","timestamp":"2025-10-14T17:00:00"}' \
  http://localhost:5000/api/v1/logs

# 7. Get time logs
curl -H "X-API-Key: bt-abc123" \
  "http://localhost:5000/api/v1/logs?badge=EMP001&start_date=2025-10-14&end_date=2025-10-14"
```

---

## 📞 Support

For API issues or questions:

- Check server logs: `logs/server_YYYY-MM-DD.log`
- Enable debug logging in server configuration
- Review error responses for details

---

**API Version**: 1.0
**Last Updated**: October 14, 2025
**Server Version**: 2.0
