# BigTime Server API Documentation

Complete REST API reference for the BigTime Server.

**Base URL**: `http://localhost:5000`
**Version**: 1.1
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
  "company_name": "BigTime",
  "current_time": DateTime,
  "server_version": "2.1.2",
  "api_version": "1.1",
  "timezone": "America/New_York"
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
  "timezone": "America/New_York",
  "current_server": "pool.npt.org",
  "last_sync": DateTime,
  "sync_offset": 5,
  "sync_interval": 500, // ms
  "running": true,
  "current_time": "%Y-%m-%d %H:%M:%S %Z"

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

### POST /api/v1/logs

Create a new time log (clock in).

**Request**:

```http
POST /api/v1/logs HTTP/1.1
Host: localhost:5000
X-API-Key: bt-abc123def456
Content-Type: application/json

{
  "client_id": "550e8400-e29b-41d4-a716-446655440000",
  "badge": "EMP001",
  "clock_in": "2025-10-14T08:00:00",
  "device_id": "client-workstation-1",
  "device_ts": "2025-10-14T08:00:00"
}
```

**Required Fields**:

- `client_id`: Unique UUID for idempotency (client-generated)
- `badge`: Employee badge
- `clock_in`: Clock in timestamp (ISO format)

**Optional Fields**:

- `device_id`: Client device identifier
- `device_ts`: Device timestamp for debugging

**Response** (201 Created):

```json
{
  "success": true,
  "data": {
    "id": 1,
    "client_id": "550e8400-e29b-41d4-a716-446655440000",
    "created_at": "2025-10-14T08:00:00"
  }
}
```

**Response** (409 Conflict):

```json
{
  "success": false,
  "error": "Employee EMP001 already clocked in"
}
```

**Response** (Idempotent - 200 OK if client_id already exists):

```json
{
  "success": true,
  "data": {
    "id": 1,
    "client_id": "550e8400-e29b-41d4-a716-446655440000",
    "created_at": "2025-10-14T08:00:00"
  }
}
```

---

### GET /api/v1/logs

Get time logs with filtering.

**Request**:

```http
GET /api/v1/logs?badge=EMP001&start=2025-10-01&end=2025-10-14 HTTP/1.1
Host: localhost:5000
X-API-Key: bt-abc123def456
```

**Query Parameters**:

- `badge` (string): Filter by employee badge
- `start` (string): Start date (YYYY-MM-DD)
- `end` (string): End date (YYYY-MM-DD)

**Response** (200 OK):

```json
{
  "success": true,
  "data": {
    "logs": [
      {
        "id": 1,
        "client_id": "550e8400-e29b-41d4-a716-446655440000",
        "remote_id": null,
        "badge": "EMP001",
        "clock_in": "2025-10-14T08:00:00",
        "clock_out": "2025-10-14T17:00:00",
        "device_id": "client-workstation-1",
        "device_ts": "2025-10-14T08:00:00",
        "sync_state": "synced",
        "created_at": "2025-10-14T08:00:00",
        "updated_at": "2025-10-14T17:00:00"
      }
    ]
  }
}
```

---

### PUT /api/v1/logs/{log_id}

Update an existing time log (clock out).

**Request**:

```http
PUT /api/v1/logs/1 HTTP/1.1
Host: localhost:5000
X-API-Key: bt-abc123def456
Content-Type: application/json

{
  "clock_out": "2025-10-14T17:00:00",
  "device_id": "client-workstation-1"
}
```

**Parameters**:

- `clock_out` (optional): Clock out timestamp (ISO format)
- `device_id` (optional): Device identifier

**Response** (200 OK):

```json
{
  "success": true,
  "data": {
    "id": 1,
    "updated": true
  }
}
```

**Response** (404 Not Found):

```json
{
  "success": false,
  "error": "Log not found"
}
```

---

### DELETE /api/v1/logs/{log_id}

Delete a time log entry.

**Request**:

```http
DELETE /api/v1/logs/1 HTTP/1.1
Host: localhost:5000
X-API-Key: bt-abc123def456
```

**Response** (200 OK):

```json
{
  "success": true,
  "data": {
    "id": 1,
    "deleted": true
  }
}
```

**Response** (404 Not Found):

```json
{
  "success": false,
  "error": "Log not found"
}
```

---

## ❌ Error Responses

### Standard Error Format

All errors follow this format:

```json
{
  "success": false,
  "error": "Error message here"
}
```

### HTTP Status Codes

| Code | Meaning               | Description                             |
| ---- | --------------------- | --------------------------------------- |
| 200  | OK                    | Request successful                      |
| 201  | Created               | Resource created successfully           |
| 400  | Bad Request           | Invalid request data                    |
| 401  | Unauthorized          | Invalid or missing API key              |
| 404  | Not Found             | Resource not found                      |
| 409  | Conflict              | Duplicate resource or invalid state     |
| 500  | Internal Server Error | Server error                            |

### Common Error Examples

**401 Unauthorized**:

```json
{
  "success": false,
  "error": "Invalid API key"
}
```

**400 Bad Request**:

```json
{
  "success": false,
  "error": "Missing required field: badge"
}
```

**409 Conflict**:

```json
{
  "success": false,
  "error": "Employee EMP001 already clocked in"
}
```

**500 Internal Server Error**:

```json
{
  "success": false,
  "error": "Database error"
}
```

---

## 📊 Data Models

### Employee

```typescript
{
  id?: number,                          // Auto-generated server-side
  name: string,                         // Required
  badge: string,                        // Required, unique
  phone_number?: number,                // Optional
  pin?: string,                         // Optional (security PIN)
  department?: string,                  // Optional
  date_of_birth?: string,               // Optional (YYYY-MM-DD)
  hire_date?: string,                   // Optional (YYYY-MM-DD)
  deactivated: boolean,                 // Default: false
  ssn?: number,                         // Optional
  period: 'hourly' | 'monthly',         // Default: 'hourly'
  rate: number,                         // Default: 0.0
  created_at?: string,                  // Auto-generated (ISO timestamp)
  updated_at?: string                   // Auto-updated (ISO timestamp)
}
```

### TimeLog

```typescript
{
  id?: number,                          // Auto-generated server-side
  client_id: string,                    // Client-generated UUID (for idempotency)
  remote_id?: number,                   // Server-assigned ID
  badge: string,                        // Required, references Employee.badge
  clock_in: string,                     // Required (ISO timestamp)
  clock_out?: string,                   // Optional (ISO timestamp)
  device_id?: string,                   // Client device identifier
  device_ts?: string,                   // Device timestamp for debugging
  sync_state?: 'synced' | 'pending' | 'failed',  // Sync status
  created_at?: string,                  // Auto-generated (ISO timestamp)
  updated_at?: string                   // Auto-updated (ISO timestamp)
}
```

### ServerConfig

```typescript
{
  company_name: string,                 // Company name
  timezone: string,                     // e.g., 'America/New_York'
  enable_ntp: boolean,                  // Enable NTP sync
  ntp_server: string,                   // NTP server address
  sync_interval: number                 // Sync interval in seconds
}
```

### API Response

All API responses follow this format:

```typescript
{
  success: boolean,                     // Indicates success/failure
  data?: any,                           // Response data (on success)
  error?: string                        // Error message (on failure)
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

# 5. Clock in (create time log)
curl -X POST \
  -H "X-API-Key: bt-abc123" \
  -H "Content-Type: application/json" \
  -d '{"client_id":"550e8400-e29b-41d4-a716-446655440000","badge":"EMP001","clock_in":"2025-10-14T08:00:00","device_id":"client-1"}' \
  http://localhost:5000/api/v1/logs

# 6. Clock out (update time log)
curl -X PUT \
  -H "X-API-Key: bt-abc123" \
  -H "Content-Type: application/json" \
  -d '{"clock_out":"2025-10-14T17:00:00"}' \
  http://localhost:5000/api/v1/logs/1

# 7. Get time logs
curl -H "X-API-Key: bt-abc123" \
  "http://localhost:5000/api/v1/logs?badge=EMP001&start=2025-10-14&end=2025-10-14"

# 8. Get all employees
curl -H "X-API-Key: bt-abc123" \
  http://localhost:5000/api/v1/employees

# 9. Get employee by badge
curl -H "X-API-Key: bt-abc123" \
  "http://localhost:5000/api/v1/employees/EMP001"

# 10. Update employee
curl -X PUT \
  -H "X-API-Key: bt-abc123" \
  -H "Content-Type: application/json" \
  -d '{"department":"Management","rate":28.00}' \
  http://localhost:5000/api/v1/employees/EMP001

# 11. Delete employee (soft delete)
curl -X DELETE \
  -H "X-API-Key: bt-abc123" \
  http://localhost:5000/api/v1/employees/EMP001
```

### Idempotent Clock In Example

Time logs use client-generated UUIDs to ensure idempotency. If the same client_id is sent twice, the server returns the existing log:

```bash
# First request (creates log)
curl -X POST \
  -H "X-API-Key: bt-abc123" \
  -H "Content-Type: application/json" \
  -d '{
    "client_id":"550e8400-e29b-41d4-a716-446655440000",
    "badge":"EMP001",
    "clock_in":"2025-10-14T08:00:00"
  }' \
  http://localhost:5000/api/v1/logs

# Response (201 Created)
{
  "success": true,
  "data": {
    "id": 1,
    "client_id": "550e8400-e29b-41d4-a716-446655440000",
    "created_at": "2025-10-14T08:00:00"
  }
}

# Second request with same client_id (returns existing log)
curl -X POST \
  -H "X-API-Key: bt-abc123" \
  -H "Content-Type: application/json" \
  -d '{
    "client_id":"550e8400-e29b-41d4-a716-446655440000",
    "badge":"EMP001",
    "clock_in":"2025-10-14T08:00:00"
  }' \
  http://localhost:5000/api/v1/logs

# Response (200 OK - idempotent, returns same log)
{
  "success": true,
  "data": {
    "id": 1,
    "client_id": "550e8400-e29b-41d4-a716-446655440000",
    "created_at": "2025-10-14T08:00:00"
  }
}
```

---

## 📞 Support

For API issues or questions:

- Check server logs: `logs/server_YYYY-MM-DD.log`
- Enable debug logging in server configuration
- Review error responses for details

---

**API Version**: 1.1
**Last Updated**: December 11, 2025
**Server Version**: 2.1.2
