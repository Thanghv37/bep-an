import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load secrets từ file .env (chỉ tồn tại trên dev). Trên prod, env var được
# set trực tiếp trong systemd service nên file này không cần.
load_dotenv(BASE_DIR / '.env')

# SECRET_KEY: trên prod set qua systemd env var. Fallback chỉ dùng cho dev
# local — KHÔNG được dùng giá trị này trên prod (Django sẽ vẫn chạy nhưng
# session/CSRF không an toàn).
SECRET_KEY = os.getenv(
    'SECRET_KEY',
    'django-insecure-dev-only-Y*EJCSO8aV@oeAXHBFrcdS9y)V0yspgH7xgqJ5iUAg=zgF4ZPu',
)

# Mặc định an toàn (False). Dev set DJANGO_DEBUG=True trong .env để bật trace.
DEBUG = os.getenv('DJANGO_DEBUG', 'False') == 'True'

# Comma-separated. Trên prod: 'net2kitchen.viettel.pro.vn,127.0.0.1'.
# Khi DEBUG=True và chưa set env, cho phép localhost để dev khỏi 400.
_allowed_hosts_env = os.getenv('DJANGO_ALLOWED_HOSTS', '')
if _allowed_hosts_env:
    ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts_env.split(',') if h.strip()]
elif DEBUG:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1']
else:
    ALLOWED_HOSTS = []

# =========================
# APPS
# =========================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'accounts',
    'core',
    'meals',
    'finance',
    'reports',
    'reviews',
    'registrations',
]

# =========================
# MIDDLEWARE
# =========================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

# =========================
# TEMPLATES
# =========================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.approval_counts',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# =========================
# DATABASE (POSTGRESQL)
# =========================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'bep_an',
        'USER': 'postgres',
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': '127.0.0.1',
        'PORT': '5432',
    }
}

# =========================
# PASSWORD VALIDATION
# =========================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# =========================
# INTERNATIONALIZATION
# =========================
LANGUAGE_CODE = 'vi'
TIME_ZONE = 'Asia/Ho_Chi_Minh'

USE_I18N = True
USE_TZ = True

# =========================
# STATIC & MEDIA
# =========================
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'static_root'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# =========================
# AUTH
# =========================
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'