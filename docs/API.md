# Локальний API

OpenAPI: `http://127.0.0.1:8000/docs`. Усі шляхи мають префікс `/api/v1`.

`POST /profiles` створює випадковий псевдонім і bearer token. Авторизовані `GET/POST/DELETE /consent`, `POST /events`, `POST /recommendations`, `POST /recommendations/{id}/accept|reject|undo`, `POST /study/trials`, `GET /export/me`, `DELETE /profile/me`. Публічні `GET /health`, `GET /layouts`.

Pydantic відхиляє невідомі поля. Без згоди `POST /events` і `POST /study/trials` повертають 403. Рекомендація не змінює макет. Модель, навчена на synthetic, доступна тільки з `synthetic_mode=true` і позначається demo. API слухає лише `127.0.0.1`; CORS дозволяє локальний Vite. Авторизація через заголовок, без cookies і CSRF-залежності. Для публічного розгортання потрібна окрема перевірка безпеки.
