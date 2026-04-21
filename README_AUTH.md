# Authentication Guide (JWT + HttpOnly Refresh Cookie)

This document explains **how authentication works in your Promise CRM project**. It is written for developers who are still learning Python (Django) or React.

Your project has **two folders**:

- **Backend:** `promise_backend` (Django + Django REST Framework)
- **Frontend:** `promise-client` (React + Vite + axios)

Paths below use these names. If your folders live elsewhere, adjust paths in your head.

---

## 1. Overview

### What we use

| Piece | Role |
|--------|------|
| **Access token** (JWT) | Short-lived proof of “who you are.” Sent on each API call as `Authorization: Bearer …`. |
| **Refresh token** (JWT) | Long-lived. Used **only** to get a **new access token** when the old one expires. |
| **HttpOnly cookie** | The browser stores the **refresh token** in a cookie that **JavaScript cannot read**. |

### Why this design?

1. **Security:** If a bad script (XSS) runs in the browser, it **cannot read** the refresh token from an HttpOnly cookie. It *can* read `localStorage`, so we **do not** put the refresh token there.
2. **Short access token:** If someone steals the access token, it works only for a **short time** (default 15 minutes in settings).
3. **Refresh rotation:** Each time you refresh, the old refresh token can be **blacklisted** and a new one issued. Stolen refresh tokens stop working sooner.
4. **Scalable pattern:** Same idea used by many SPAs: access in memory (or short storage) + refresh in HttpOnly cookie + standard JWT libraries (SimpleJWT on Django).

### Trade-off we accepted on the frontend

The access token is also saved in **`sessionStorage`** so a **full page reload (F5)** still keeps you logged in without always calling refresh first. That is slightly easier for XSS to read than “memory only,” but much better than putting the **refresh** token in `localStorage`. You can remove `sessionStorage` later if you want stricter security.

---

## 2. Authentication Flow (Step by Step)

### A. User logs in

1. User opens the React app (e.g. `http://localhost:5173/login`) and enters **email** and **password**.
2. React sends `POST` to the Django API: `/api/login/` with `credentials: true` so cookies can be set.

### B. Backend verifies credentials

1. Django runs `authenticate(username=email, password=password)` in `api/views.py` → function **`login_user`**.
2. Your project uses **`EmailBackend`** (`api/backends.py`) so “username” for login is actually the **email**.

### C. Backend generates Access Token + Refresh Token

1. On success, code calls `RefreshToken.for_user(user)` from **djangorestframework-simplejwt**.
2. That object has:
   - `.access_token` → encoded **access** JWT  
   - str(refresh) → encoded **refresh** JWT  

### D. Refresh token stored in HttpOnly cookie

1. **`set_refresh_cookie(response, refresh_str)`** in `api/cookie_auth.py` adds a `Set-Cookie` header.
2. Cookie name default: **`refresh_token`** (see `JWT_REFRESH_COOKIE_NAME` in `crm_pro/settings.py`).
3. Flags: **HttpOnly**, **SameSite** (default `Lax`), **Secure** in production (see settings).

### E. Access token returned to frontend

1. JSON body includes **`access`** and **`user`** (id, email, username).
2. The **refresh** string is **not** in the JSON (only in the cookie).

### F. Frontend stores access token and calls APIs

1. **`setAccessToken`** in `promise-client/src/lib/authToken.ts` saves the access token in memory **and** `sessionStorage` (key: `promise_access_token`).
2. **`apiClient`** (`promise-client/src/lib/apiClient.ts`) adds:
   - `Authorization: Bearer <access>` on every request  
   - `withCredentials: true` so the browser sends the **cookie** to Django.

### G. When access token expires

1. A normal API call returns **401 Unauthorized**.
2. axios **response interceptor** in `apiClient.ts` catches 401.
3. It calls **`refreshAccessToken()`** → `POST /api/auth/token/refresh/` with **no** refresh in the body; the browser sends the **HttpOnly cookie** automatically.
4. Backend **`CookieTokenRefreshView`** (`api/token_views.py`) reads the cookie, validates, returns `{ "access": "..." }`.
5. Frontend saves the new access token and **retries** the failed request once.

### H. Logout

1. User clicks **Log out** in `promise-client/src/layouts/AdminLayout.tsx`.
2. Frontend calls **`logout()`** in `promise-client/src/features/auth/authApi.ts` → `POST /api/logout/`.
3. Backend **`logout_user`** reads refresh from cookie (or old JSON field), **blacklists** it, clears cookie with **`clear_refresh_cookie`**.
4. Frontend clears access token and broadcasts **logout** to other tabs (see section 5).

---

## 3. APIs Implemented

All paths below are under Django’s **`/api/`** prefix (see `crm_pro/urls.py` → `path("api/", include("api.urls"))`).

### 3.1 `POST /api/login/`

| | |
|---|--|
| **Purpose** | Check email/password and start a session (access JWT + refresh cookie). |
| **Who can call** | Anyone (`AllowAny`). |
| **Request body (JSON)** | `{ "email": "you@example.com", "password": "your-password" }` |
| **Success response (example)** | `{ "message": "Login successful", "access": "<jwt-access>", "user": { "id": 1, "email": "...", "username": "..." } }` |
| **Response headers** | `Set-Cookie: refresh_token=...` (HttpOnly, etc.) |
| **Inside Django** | `login_user` in `api/views.py` → `authenticate` → `RefreshToken.for_user` → `set_refresh_cookie`. |
| **Failure** | `401` with `{ "error": "Invalid credentials" }` |

### 3.2 `POST /api/auth/token/refresh/` (this is your “refresh” API)

| | |
|---|--|
| **Purpose** | Issue a **new access token** using the refresh token from the **cookie**. |
| **Who can call** | Anyone (`AllowAny`) — possession of valid cookie matters. |
| **Request body** | Empty JSON `{}` is enough; refresh comes from **cookie**. |
| **Success response (example)** | `{ "access": "<new-jwt-access>" }` |
| **Response headers** | If rotation is on, may set a **new** `refresh_token` cookie. |
| **Inside Django** | `CookieTokenRefreshView.post` in `api/token_views.py` → reads `request.COOKIES` → `TokenRefreshSerializer` from SimpleJWT. |
| **Failure** | `401` with `{"detail": "..."}` and cookie cleared on invalid refresh. |

> Note: The path is **`/api/auth/token/refresh/`**, not `/api/refresh/`.

### 3.3 `POST /api/logout/`

| | |
|---|--|
| **Purpose** | Invalidate refresh token (blacklist) and remove cookie. |
| **Who can call** | `AllowAny` (so you can log out even if access token is already expired). |
| **Request body** | Usually empty; optional legacy `{ "refresh": "..." }`. |
| **Success response (example)** | `{ "message": "Logout successful" }` |
| **Inside Django** | `logout_user` in `api/views.py` → read cookie → `RefreshToken(...).blacklist()` → `clear_refresh_cookie`. |

### 3.4 Profile (not named `/me`)

| | |
|---|--|
| **Purpose** | Read or update the logged-in user’s profile (`CustomUser` via `user_profile`). |
| **URL** | **`GET` / `PUT` / `PATCH`** → `/api/user_profile/` |
| **Who can call** | Logged-in users (`IsAuthenticated`). |
| **Request** | For `PUT`/`PATCH`, JSON body matches `UserProfileSerializer` in `api/serializers.py`. |
| **Header** | `Authorization: Bearer <access>` |
| **Inside Django** | `user_profile` in `api/views.py`. |

### 3.5 “Protected” APIs (everything else)

Examples: `/api/dashboard/stats/`, `/leads/...`, etc.

| | |
|---|--|
| **Purpose** | Normal business logic. |
| **Rule** | Default in `crm_pro/settings.py`: `DEFAULT_PERMISSION_CLASSES` = `IsAuthenticated`. |
| **Header** | `Authorization: Bearer <access>` |
| **If access expired** | 401 → frontend refresh flow (section 2.G). |

---

## 4. Backend Code Explanation (`promise_backend`)

### 4.1 `crm_pro/settings.py`

**Why it matters:** Tells Django how long tokens live, CORS, and cookie behavior.

| Setting / block | What it does |
|------------------|--------------|
| `CORS_ALLOWED_ORIGINS` | Lists **exact** frontend URLs allowed (e.g. `http://localhost:5173`). Required when using cookies + `credentials`. |
| `CORS_ALLOW_CREDENTIALS = True` | Browser may send cookies on cross-origin requests to this API. |
| `CORS_ALLOW_ALL_ORIGINS = False` | Must be false when using credentials. |
| `CSRF_TRUSTED_ORIGINS` | Trusts the frontend origin for CSRF-related checks where needed. |
| `REST_FRAMEWORK` | Uses `JWTAuthentication` so DRF reads the **Bearer** access token. |
| `SIMPLE_JWT` | Access lifetime (default **15 min** via `JWT_ACCESS_MINUTES`), refresh lifetime (default **7 days** via `JWT_REFRESH_DAYS`), **rotate** + **blacklist** after rotation. |
| `JWT_REFRESH_COOKIE_NAME`, `JWT_COOKIE_SECURE`, `JWT_COOKIE_SAMESITE`, `JWT_REFRESH_COOKIE_MAX_AGE` | Controls the refresh **cookie** name, HTTPS-only flag, SameSite, and max-age. |

### 4.2 `api/cookie_auth.py` (new file)

Small helpers so cookie rules stay in one place.

| Function | What it does |
|----------|----------------|
| `refresh_cookie_name()` | Returns the cookie name (default `refresh_token`). |
| `set_refresh_cookie(response, token)` | Adds `Set-Cookie` with **HttpOnly**, **path**, **max_age**, **secure**, **samesite**. |
| `clear_refresh_cookie(response)` | Deletes the cookie (must use same path/samesite as when set). |

### 4.3 `api/token_views.py` (new file)

| Class / method | What it does |
|----------------|----------------|
| `CookieTokenRefreshView` | DRF `APIView` for `POST /api/auth/token/refresh/`. |
| `.post()` | Reads refresh JWT from **cookie** → `TokenRefreshSerializer` validates and builds new access (and new refresh if rotation enabled) → returns **only** `{ "access": ... }` in JSON → if rotated, calls `set_refresh_cookie` with the **new** refresh. |

### 4.4 `api/views.py` (updated)

| Function | What it does |
|----------|----------------|
| `login_user` | Validates user → builds tokens → JSON has **access** + **user** → **`set_refresh_cookie`** for refresh. |
| `logout_user` | Reads refresh from **cookie** (or legacy body) → **blacklist** → **`clear_refresh_cookie`**. Uses `AllowAny` so logout still works if access is expired. |
| `user_profile` | Decorated with `@api_view(['GET','PUT','PATCH'])` and `IsAuthenticated` for profile CRUD. |
| `test_api` | Public health-style endpoint with `AllowAny`. |

**JWT generation:** `RefreshToken.for_user(user)` (SimpleJWT) inside `login_user`.

### 4.5 `api/urls.py` (updated)

Adds:

```text
path("auth/token/refresh/", CookieTokenRefreshView.as_view(), ...)
```

Other routes (`login/`, `logout/`, `user_profile/`, etc.) were already listed here.

### 4.6 `api/backends.py` (existing)

`EmailBackend` — allows logging in with **email** as the username passed to `authenticate`.

---

## 5. Frontend Code Explanation (`promise-client`)

### 5.1 `src/features/auth/LoginPage.tsx`

- Simple form: email + password.
- On submit → **`login()`** from `authApi.ts`.
- On success → `navigate("/", { replace: true })` to the main app.

### 5.2 `src/features/auth/authApi.ts`

| Function | What it does |
|----------|----------------|
| `login(email, password)` | `rawClient.post("/api/login/")` → **`setAccessToken`** → **`broadcastAuth({ type: "login" })`** for other tabs. |
| `logout()` | `rawClient.post("/api/logout/")` → **`setAccessToken(null)`** → **`broadcastAuth({ type: "logout" })`**. |
| `tryRestoreSession()` | If no access in memory/storage, calls **`refreshAccessToken()`** once; uses a **single shared promise** so React Strict Mode does not double-refresh and break rotation. |

### 5.3 `src/lib/authToken.ts`

| Piece | What it does |
|-------|----------------|
| `getAccessToken` / `setAccessToken` | In-memory variable + **`sessionStorage`** key `promise_access_token`. |
| `broadcastAuth` / `subscribeAuth` | Uses **`BroadcastChannel("promise-auth")`** so one tab can tell others “login” or “logout”. |

### 5.4 `src/lib/apiClient.ts`

| Piece | What it does |
|-------|----------------|
| `API_BASE` | From `import.meta.env.VITE_API_URL` or default `http://127.0.0.1:8000`. |
| `rawClient` | axios instance with **`withCredentials: true`**, **no** 401 retry loop — used for login, refresh, logout. |
| `refreshAccessToken()` | `POST /api/auth/token/refresh/` via `rawClient`. |
| `apiClient` | Same `withCredentials`; **request** interceptor adds `Authorization: Bearer …`. |
| **Response interceptor** | On **401**: skip if URL is login or refresh; else run **one** shared `refreshPromise`; on success retry request; on failure **`setAccessToken(null)`** + **`broadcastAuth({ type: "logout" })`**. |

### 5.5 `src/features/auth/AuthProvider.tsx`

- Subscribes to **`subscribeAuth`**: on **logout**, clears token and navigates to `/login`.
- On **login** broadcast, calls **`tryRestoreSession()`** so other tabs pick up access via refresh cookie.
- On first load, **`tryRestoreSession()`** if needed, then sets **`AuthReadyProvider`** to ready.

### 5.6 `src/features/auth/authReadyContext.tsx` + `ProtectedRoute.tsx`

- **`AuthReadyProvider`** wraps the app with `ready` flag so we do not flash “unauthorized” before bootstrap finishes.
- **`ProtectedRoute`** shows loader until ready; if still no access token → redirect to **`/login`**.

### 5.7 `src/main.tsx`

Wraps `<App />` with `<BrowserRouter>` → **`<AuthProvider>`** so auth logic runs for all routes.

### 5.8 `src/App.tsx`

- Route **`/login`** → `LoginPage`.
- Protected layout tree: **`ProtectedRoute`** → **`AdminLayout`** → feature routes.

### 5.9 `src/layouts/AdminLayout.tsx`

- **“Log out”** button calls **`logout()`** then **`navigate("/login")`**.

### 5.10 Multi-tab sync (implemented)

| Event | What happens |
|-------|----------------|
| Login in tab A | `broadcastAuth({ type: "login" })` → tab B runs `tryRestoreSession()` → new access using shared refresh cookie. |
| Logout in tab A | `broadcastAuth({ type: "logout" })` → tab B clears token and goes to `/login`. |
| Refresh fails in one tab | Interceptor broadcasts logout → other tabs react via `AuthProvider`. |

---

## 6. Security Benefits (Simple Words)

| Topic | Why it helps |
|-------|----------------|
| **HttpOnly cookie for refresh** | JavaScript cannot read it, so a typical XSS script cannot copy-paste your refresh token to an attacker. |
| **Short-lived access token** | Stolen access token works only a short time (default 15 minutes). |
| **Refresh rotation + blacklist** | Old refresh tokens stop working after refresh/logout, so leaked tokens have a shorter life. |
| **Not putting refresh in `localStorage`** | `localStorage` is fully readable by JS → bad for long-lived refresh. |
| **XSS** | HttpOnly helps a lot for refresh; access in memory/`sessionStorage` is still visible to XSS — there is no perfect fix in the browser, only trade-offs. |
| **CSRF** | `SameSite=Lax` (default) reduces sending cookies on random cross-site POSTs; production often uses HTTPS + stricter policies. |

---

## 7. How to Run the Project

### Backend (`promise_backend`)

```bash
cd promise_backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements-server.txt
python manage.py migrate
python manage.py createsuperuser  # create first user (use email as username)
python manage.py runserver
```

API base: **`http://127.0.0.1:8000`** (or `http://localhost:8000` — pick one and match the frontend env).

### Frontend (`promise-client`)

```bash
cd promise-client
cp .env.example .env                # optional
# Edit .env: VITE_API_URL=http://127.0.0.1:8000   (must match how you open the API)
npm install
npm run dev
```

Open **`http://localhost:5173`** (or the URL Vite prints).

### Environment variables

**Backend (optional, examples):**

| Variable | Meaning |
|----------|---------|
| `CORS_ALLOWED_ORIGINS` | Comma-separated list, must include your Vite origin. |
| `CSRF_TRUSTED_ORIGINS` | Same idea for CSRF trusted list. |
| `JWT_ACCESS_MINUTES` | Access token lifetime (minutes). |
| `JWT_REFRESH_DAYS` | Refresh token lifetime (days). |
| `JWT_COOKIE_SECURE` | `true` / `1` / `yes` to force Secure cookies (HTTPS). |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hosts. |

**Frontend:**

| Variable | Meaning |
|----------|---------|
| `VITE_API_URL` | Backend origin **without** trailing slash, e.g. `http://127.0.0.1:8000`. |

### Cookies in local development

- Use **HTTP** on localhost → `JWT_COOKIE_SECURE` is **False** when `DEBUG=True` (unless you force it), so cookies work.
- Use the **same host style** for API and cookie: do not mix `localhost` and `127.0.0.1` for the API URL vs the page, or the cookie may not be sent where you expect.

---

## 8. Common Issues & Fixes

| Problem | What to check |
|---------|----------------|
| **Cookie not set** | `withCredentials: true` on axios; `CORS_ALLOW_CREDENTIALS=True`; origin in `CORS_ALLOWED_ORIGINS`; not using `*` for CORS with credentials. |
| **CORS error in browser** | Add exact frontend URL to `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS`; restart Django after changing `.env`. |
| **401 after refresh** | Refresh cookie missing or blacklisted — log in again; check `ROTATE_REFRESH_TOKENS` + double refresh race (we dedupe in `tryRestoreSession`). |
| **Infinite refresh loop** | Interceptor must **skip** `/api/auth/token/refresh/` and `/api/login/` (already done in `apiClient.ts`). |
| **Logout does not “feel” logged out** | Ensure `logout()` runs and `setAccessToken(null)` clears `sessionStorage`; hard refresh once to test. |
| **Reload sends me to login** | Ensure `VITE_API_URL` matches the server that set the cookie; check cookie in DevTools → Application → Cookies. |

---

## 9. Simple Diagram (Text)

```text
[ React Login Page ]
        |
        | POST /api/login/  +  credentials: include
        v
[ Django login_user ]
        |
        |-- verifies email/password
        |-- creates JWT access + JWT refresh
        |
        |-- HTTP response:
              JSON: { access, user }
              Set-Cookie: refresh_token=... (HttpOnly)
        v
[ React stores access in memory + sessionStorage ]
        |
        | GET /api/...  +  Header: Authorization: Bearer <access>
        |                 +  credentials: include (cookie sent)
        v
[ Django DRF + JWTAuthentication ] --> 200 OK

        (time passes, access expires)

[ React api call ] --> 401
        |
        | POST /api/auth/token/refresh/  (cookie only)
        v
[ CookieTokenRefreshView ] --> { access: new... }
        |
        v
[ React retries original request with new access ]

[ User clicks Log out ]
        |
        | POST /api/logout/
        v
[ Django blacklist + clear cookie ]
        |
        v
[ React clears access + BroadcastChannel logout ]
```

---

## 10. Important Notes Before You Change Auth Code

1. **Do not return the refresh token in JSON** from `login_user` — keep it in the **HttpOnly cookie** only (unless you have a very good reason and redesign security).

2. **If you change cookie name or path**, update **`set_refresh_cookie`** and **`clear_refresh_cookie`** together, or logout will leave “ghost” cookies.

3. **If you add new “public” API views**, add `AllowAny` (or they stay locked by global `IsAuthenticated`).

4. **If you change `SIMPLE_JWT` lifetimes**, consider updating **`JWT_REFRESH_COOKIE_MAX_AGE`** so cookie lifetime matches refresh JWT lifetime.

5. **Frontend:** any new axios instance that calls the API should use **`withCredentials: true`** and the same **`API_BASE`**, or cookies will not go with the request.

6. **Interceptor:** never use `apiClient` inside the refresh function — use **`rawClient`** — or you can cause infinite loops.

7. **Two repos:** deploy backend and frontend with **matching** URLs in CORS and `VITE_API_URL`.

---

## Quick reference — files touched

| Area | File |
|------|------|
| Backend settings | `crm_pro/settings.py` |
| Cookie helpers | `api/cookie_auth.py` |
| Refresh endpoint | `api/token_views.py` |
| Login / logout / profile | `api/views.py` |
| URL routes | `api/urls.py` |
| Email login | `api/backends.py` (existing) |
| Frontend axios | `src/lib/apiClient.ts` |
| Token storage + tabs | `src/lib/authToken.ts` |
| Login / logout API wrappers | `src/features/auth/authApi.ts` |
| Bootstrap + tab listener | `src/features/auth/AuthProvider.tsx` |
| Ready flag | `src/features/auth/authReadyContext.tsx` |
| Guard routes | `src/features/auth/ProtectedRoute.tsx` |
| Login UI | `src/features/auth/LoginPage.tsx` |
| Router | `src/App.tsx`, `src/main.tsx` |
| Logout button | `src/layouts/AdminLayout.tsx` |
| Env example | `promise-client/.env.example` |

---

You now have a map from **browser button** → **HTTP** → **Django file** → **token/cookie** and back. When in doubt, search this repo for the function names in the tables above.
