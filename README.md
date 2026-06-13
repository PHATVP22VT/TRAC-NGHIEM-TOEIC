# TOEIC Quiz Maker — Web App

Chạy được trên **điện thoại, iPad, máy tính** qua trình duyệt. Không cần cài PyQt5.

---

## Chạy local (PC làm server, điện thoại cùng WiFi)

```bash
pip install flask google-generativeai gunicorn
python app.py
```

Mở trình duyệt điện thoại: `http://<IP_PC>:5000`  
(Tìm IP PC: Windows → `ipconfig`, Mac/Linux → `ifconfig`)

---

## Deploy lên Render (không cần PC bật)

1. Tạo tài khoản tại https://render.com
2. New → Web Service → Connect GitHub repo chứa code này
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `gunicorn app:app`
5. Thêm Environment Variable: `SECRET_KEY` = một chuỗi ngẫu nhiên
6. **Không** hardcode API key — nhập trực tiếp trên giao diện web

---

## Deploy lên Railway

```bash
# Cài Railway CLI
npm install -g @railway/cli
railway login
railway init
railway up
```

---

## Lưu ý quan trọng

- Quiz được lưu trên **server** (file JSON trong `~/.toeic_quiz_web/quizzes/`)
- Trên Render free tier: data bị xóa khi redeploy → dùng Render Disk hoặc chuyển sang SQLite
- API key Gemini nhập qua giao diện (không lưu permanent, chỉ giữ trong session)
- Để lưu key permanent trên cloud: đặt biến môi trường `GEMINI_API_KEY` trên Render
