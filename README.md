# Social Media API with AI Detection

Backend API cho nền tảng mạng xã hội với tính năng phát hiện nội dung AI-generated.

## 🚀 Tính năng

- ✅ Authentication (Sign up, Login)
- ✅ User Profiles
- ✅ Posts (Create, Read, Update, Delete)
- ✅ Media Upload (Images, Videos)
- ✅ Likes
- ✅ Notifications
- ✅ AI Content Detection (DINOv2)
- ✅ Admin Dashboard
- ✅ Row Level Security với Supabase

## 📋 Yêu cầu

- Python 3.9+
- Supabase account
- PyTorch (CPU hoặc GPU)

## 🛠️ Cài đặt

### 1. Clone repository
```bash
git clone <your-repo>
cd <project-folder>
```

### 2. Tạo virtual environment
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# hoặc
venv\Scripts\activate  # Windows
```

### 3. Cài đặt dependencies
```bash
pip install -r requirements.txt
```

### 4. Cấu hình môi trường

Tạo file `.env`:
```env
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
SUPABASE_SERVICE_KEY=your_supabase_service_role_key
JWT_SECRET=your_jwt_secret
JWT_ALGORITHM=HS256
STORAGE_BUCKET=media

MODEL_PATH=ml_models/best_model.pth
DEVICE=cpu
```

### 5. Setup Supabase

1. Tạo project trên [Supabase](https://supabase.com)
2. Chạy SQL script trong `database_schema.sql`
3. Tạo Storage bucket tên `media` với public access
4. Copy URL và Keys vào `.env`

### 6. Đặt model weights

Đặt file `best_model.pth` vào thư mục `ml_models/`

### 7. Chạy server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API sẽ chạy tại: `http://localhost:8000`

## 📚 API Documentation

Sau khi chạy server, truy cập:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 🔐 Authentication Flow

1. **Sign up**: `POST /auth/signup`
2. **Login**: `POST /auth/login` → Nhận `access_token`
3. **Authenticated requests**: Thêm header `Authorization: Bearer <access_token>`

## 📝 Ví dụ sử dụng

### Đăng ký
```bash
curl -X POST "http://localhost:8000/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password123",
    "username": "johndoe"
  }'
```

### Tạo post
```bash
curl -X POST "http://localhost:8000/posts" \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Hello World!",
    "is_private": false
  }'
```

### Upload media
```bash
curl -X POST "http://localhost:8000/posts/<post_id>/media" \
  -H "Authorization: Bearer <your_token>" \
  -F "file=@/path/to/image.jpg"
```

### Check AI
```bash
curl -X POST "http://localhost:8000/posts/<post_id>/check_ai" \
  -H "Authorization: Bearer <your_token>"
```

## 🏗️ Kiến trúc
```
├── app/
│   ├── routers/          # API endpoints
│   ├── models/           # Pydantic models
│   ├── services/         # Business logic
│   └── utils/            # Helper functions
├── ml_models/            # AI detection model
└── .env                  # Configuration
```

## 🧪 Testing
```bash
# TODO: Add tests
pytest
```

## 📊 Database Schema

Xem chi tiết trong file SQL đã cung cấp. Bao gồm:
- `profiles` - User profiles
- `posts` - Posts
- `post_media` - Media files
- `post_likes` - Likes
- `notifications` - Notifications

## 🔒 Security

- Row Level Security (RLS) enabled
- JWT authentication
- Owner-based access control
- Admin privileges

## 📈 Performance

- Caching với `@lru_cache`
- Batch operations
- Efficient queries
- CDN cho media files

## 🚧 TODO

- [ ] Add tests
- [ ] Rate limiting
- [ ] WebSocket for real-time notifications
- [ ] Elasticsearch for search
- [ ] Redis caching
- [ ] Background tasks với Celery

## 📄 License

MIT

## 👥 Contributors

Your Name