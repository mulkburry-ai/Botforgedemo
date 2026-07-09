# 🤖 BotForge — Telegram Shop Bot Template

Python + aiogram 3.x + Neon PostgreSQL + Render

---

## 📋 Talablar

- Python 3.11+
- [Neon](https://neon.tech) — bepul PostgreSQL
- [Render](https://render.com) — bepul hosting
- [UptimeRobot](https://uptimerobot.com) — bot uyquga ketmasligi uchun
- Telegram bot token — [@BotFather](https://t.me/BotFather)

---

## ⚡ O'rnatish — Qadam-baqadam

### 1. Reponi klonlash

```bash
git clone https://github.com/sizning-repo/botforge.git
cd botforge
```

### 2. Virtual muhit va kutubxonalar

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. `.env` fayl yaratish

```bash
cp .env.example .env
```

`.env` faylini oching va quyidagilarni to'ldiring:

```env
BOT_TOKEN=1234567890:ABCdef...
DATABASE_URL=postgresql://user:pass@ep-xxx.neon.tech/dbname?sslmode=require
ADMIN_ID=123456789
ADMIN_USERNAME=@sizning_username
```

> **`ADMIN_ID`** ni bilish: [@userinfobot](https://t.me/userinfobot) ga `/start` yuboring.

### 4. Neon da bazani sozlash

1. [neon.tech](https://neon.tech) ga kiring
2. Yangi loyiha yarating
3. **SQL Editor** ni oching
4. `schema.sql` faylini nusxalab joylashtiring
5. **Run** tugmasini bosing

Chap tomonda 10 ta jadval paydo bo'lishi kerak:
`users`, `categories`, `products`, `variants`, `orders`, `order_items`, `cart`, `favorites`, `last_seen`, `settings`

### 5. Lokal test

```bash
python main.py
```

Bot polling rejimida ishga tushadi. `/start` va `/admin` buyruqlarini sinab ko'ring.

---

## 🚀 Render da Deploy

### 1. GitHub ga yuklash

```bash
git add .
git commit -m "Initial commit"
git push origin main
```

### 2. Render da yangi servis

1. [render.com](https://render.com) → **New** → **Web Service**
2. GitHub reponi ulang
3. Quyidagilarni to'ldiring:

| Maydon | Qiymat |
|---|---|
| Name | botforge |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python main.py` |

4. **Environment Variables** bo'limida `.env` dagi barcha qiymatlarni qo'shing
5. `WEBHOOK_HOST` ga Render URL ni kiriting:
   ```
   WEBHOOK_HOST=https://sizning-bot.onrender.com
   ```
6. **Create Web Service** tugmasini bosing

### 3. Deploy tekshirish

Render dashboard da **Logs** bo'limini oching. Quyidagi xabarlar ko'rinishi kerak:

```
✅ config.py yuklandi
✅ Neon PostgreSQL pool yaratildi
✅ Scheduler ishga tushdi
✅ Webhook o'rnatildi
🟢 Bot ishga tushdi!
```

---

## ⏰ UptimeRobot sozlash

Render bepul tarif 15 daqiqa so'rov bo'lmasa botni uxlatadi.
UptimeRobot har 5 daqiqada ping yuborib uxlatmaslik uchun:

1. [uptimerobot.com](https://uptimerobot.com) ga kiring
2. **Add New Monitor** → **HTTP(s)**
3. URL: `https://sizning-bot.onrender.com/health`
4. Interval: **5 minutes**
5. **Create Monitor**

---

## 📁 Fayl tuzilmasi

```
botforgedemo/
│
├── main.py              # Bot ishga tushirish
├── config.py            # .env validatsiya
├── scheduler.py         # Chegirma, bekap, stok ogohlantirish
│
├── db/                  # Barcha DB so'rovlari
│   ├── pool.py          # Neon ulanish
│   ├── categories.py
│   ├── products.py
│   ├── orders.py
│   ├── users.py
│   └── stats.py
│
├── handlers/            # Bot handlerlari
│   ├── common.py        # /start, /admin
│   ├── catalog.py       # Katalog
│   ├── cart.py          # Savat, buyurtma
│   ├── profile.py       # Buyurtmalarim
│   ├── info.py          # Ma'lumot bo'limi
│   └── admin/           # Admin handlerlari
│       ├── panel.py
│       ├── products.py
│       ├── orders.py
│       ├── users.py
│       └── stats.py
│
├── keyboards/           # Barcha tugmalar (CallbackData)
│   ├── user.py
│   └── admin.py
│
├── utils/               # Yordamchi funksiyalar
│   ├── formatters.py    # Narx, sana, holat formatlash
│   ├── validators.py    # Input tekshirish
│   └── broadcast.py     # Ommaviy xabar
│
├── middlewares/
│   └── rate_limit.py    # Spam himoya
│
├── schema.sql           # DB jadvallarini yaratish
├── .env.example         # .env namunasi
└── requirements.txt
```

---

## ⚙️ Muhim sozlamalar

### Scheduler vaqtlari

`scheduler.py` da Toshkent vaqt zonasi (`Asia/Tashkent`) ishlatiladi:

| Vazifa | Vaqt |
|---|---|
| Chegirma tekshirish | Har 1 daqiqada |
| Stok ogohlantirish | Har kuni 09:00 |
| Avtomatik bekap | Har kuni 03:00 |

### Chegirma qoidasi

```
Qiymat < 100   →  foiz (%)      misol: 30 → 30% chegirma
Qiymat >= 100  →  aniq narx     misol: 45000 → narx 45,000 so'm
```

### Stok ogohlantirish chegarasi

`settings` jadvalidagi `low_stock_threshold` qiymati (standart: 5).
Admin panelda o'zgartirish mumkin: **Ma'lumotlar > Sozlamalar**.

---

## 🔧 Yangi mijozga o'rnatish

Har bir yangi mijoz uchun:

1. `@BotFather` dan yangi bot token oling
2. Neon da yangi loyiha yarating → `schema.sql` ishga tushiring
3. Render da yangi Web Service → environment variables to'ldiring
4. UptimeRobot da yangi monitor qo'shing
5. `/admin` buyrug'i bilan panelni oching
6. **Ma'lumotlar > Sozlamalar** da do'kon ma'lumotlarini kiriting
7. **Mahsulotlar > Kategoriyalar** dan kategoriyalar qo'shing
8. Mahsulotlarni qo'shish boshlang

---

## 🐛 Muammo bo'lsa

| Muammo | Yechim |
|---|---|
| Bot ishga tushmaydi | Render Logs da xatoni ko'ring |
| DB ulanmaydi | `DATABASE_URL` ni tekshiring, Neon da `?sslmode=require` bo'lishi shart |
| Webhook ishlamaydi | `WEBHOOK_HOST` to'g'ri URL ekanini tekshiring (https://) |
| `/admin` ishlamaydi | `ADMIN_ID` to'g'ri raqam ekanini tekshiring |
| Bot uyquga ketadi | UptimeRobot `/health` ga ping yuborayotganini tekshiring |

---

## 📄 Litsenziya

Shaxsiy foydalanish va tijorat maqsadlarda sotish uchun ruxsat berilgan.
