# API Endpoint Reference (API_REFERENCE.md)

## 1. Authentication Endpoints

### `POST /api/auth/login`
*   **Method**: `POST`
*   **Authentication**: None
*   **Request Headers**: `Content-Type: application/json`
*   **Request Body**:
    ```json
    {
      "email": "admin@letatec.com",
      "password": "supersecretpassword"
    }
    ```
*   **Response Body (200 OK)**:
    ```json
    {
      "tokens": {
        "accessToken": "eyJhbG...",
        "refreshToken": "eyJhbG...",
        "tokenType": "bearer"
      },
      "user": {
        "username": "admin",
        "role": "admin"
      }
    }
    ```
*   **Errors**:
    *   `401 Unauthorized` (Invalid credentials)
    *   `403 Forbidden` (Non-admin login attempts)

---

## 2. Ingestion & Catalog Endpoints

### `POST /api/admin/knowledge/upload`
*   **Method**: `POST`
*   **Authentication**: JWT Token (requires `admin` or `super_admin` role)
*   **Request Body**: Multipart form data with `file` (binary) and `category` (string).
*   **Response Body (200 OK)**:
    ```json
    {
      "status": "success",
      "document_id": "doc_8f2a1b9c"
    }
    ```
*   **Errors**:
    *   `401 Unauthorized` (Missing token)
    *   `403 Forbidden` (Insufficient role)
    *   `400 Bad Request` (Unsupported file extension)
