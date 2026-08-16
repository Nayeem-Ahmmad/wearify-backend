import os
import dj_database_url
from pathlib import Path
from datetime import timedelta
from decouple import config
# settings.py


FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:5173')

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=lambda v: [s.strip() for s in v.split(',')])

# CSRF — needed so Django Admin login works over the Render https domain.
# Render's URL isn't known at code-write time, so it comes from an env var.
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS', default='',
    cast=lambda v: [s.strip() for s in v.split(',') if s.strip()]
)

# Application definition

INSTALLED_APPS = [

    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "unfold.contrib.import_export",

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps
    'rest_framework',
    'corsheaders',
    'rest_framework_simplejwt',
    'django_filters',
    'drf_spectacular',

    # Local apps
    'shop',
]

UNFOLD = {
    "SITE_TITLE": "Wearify Admin",
    "SITE_HEADER": "Wearify",
    "SITE_SYMBOL": "storefront",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "DASHBOARD_CALLBACK": "shop.dashboard.dashboard_callback",
    "COLORS": {
        "primary": {
            "50": "239 246 255",
            "100": "219 234 254",
            "200": "191 219 254",
            "300": "147 197 253",
            "400": "96 165 250",
            "500": "37 99 235",
            "600": "37 99 235",
            "700": "29 78 216",
            "800": "30 64 175",
            "900": "30 58 138",
            "950": "23 37 84",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": [
            {
                "title": "Dashboard",
                "items": [
                    {
                        "title": "Home",
                        "icon": "dashboard",
                        "link": "/admin/",
                    },
                ],
            },
            {
                "title": "Catalog",
                "collapsible": True,
                "items": [
                    {"title": "Products", "icon": "checkroom", "link": "/admin/shop/product/"},
                    {"title": "Categories", "icon": "category", "link": "/admin/shop/category/"},
                    {"title": "Brands", "icon": "sell", "link": "/admin/shop/brand/"},
                    {"title": "Tags", "icon": "label", "link": "/admin/shop/tag/"},
                ],
            },
            {
                "title": "Sales",
                "collapsible": True,
                "items": [
                    {"title": "Orders", "icon": "shopping_bag", "link": "/admin/shop/order/"},
                    {"title": "Payments", "icon": "payments", "link": "/admin/shop/payment/"},
                    {"title": "Carts", "icon": "shopping_cart", "link": "/admin/shop/cart/"},
                ],
            },
            {
                "title": "Promotions",
                "collapsible": True,
                "items": [
                    {"title": "Coupons", "icon": "confirmation_number", "link": "/admin/shop/coupon/"},
                    {"title": "Flash Sales", "icon": "bolt", "link": "/admin/shop/flashsale/"},
                ],
            },
            {
                "title": "Customers",
                "collapsible": True,
                "items": [
                    {"title": "Users", "icon": "person", "link": "/admin/auth/user/"},
                    {"title": "Profiles", "icon": "badge", "link": "/admin/shop/userprofile/"},
                    {"title": "Addresses", "icon": "location_on", "link": "/admin/shop/address/"},
                    {"title": "Reviews", "icon": "star", "link": "/admin/shop/review/"},
                    {"title": "Wishlists", "icon": "favorite", "link": "/admin/shop/wishlist/"},
                ],
            },
        ],
    },
}                                                                                                                                   

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 12,

    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',

    #Rate limiting/throttling 

    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '30/minute',
        'user': '100/minute',
        'register': '5/hour',
        'login': '5/minute',
        'payment': '10/minute',
    },

}


SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=7),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=15),
    'ROTATE_REFRESH_TOKENS': True,
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Whitenoise serves Django's own static files (admin CSS/JS, DRF browsable
# API assets) directly from the app process — Render's free tier has no
# separate static file server, so this is required in production.
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'shop.middleware.MaintenanceModeMiddleware', # for maintenance model 
]

ROOT_URLCONF = 'wearify.urls'

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
            ],
        },
    },
]

WSGI_APPLICATION = 'wearify.wsgi.application'


# DATABASE_URL env var (Render provides this automatically once the
# PostgreSQL add-on is connected). Falls back to local SQLite when the env
# var isn't set, so `python manage.py runserver` on your machine still works
# exactly as before — nothing changes for local development.
DATABASE_URL = config('DATABASE_URL', default='')

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            ssl_require=not DEBUG,
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Dhaka'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'

SSLCOMMERZ_STORE_ID = config('SSLCOMMERZ_STORE_ID')
SSLCOMMERZ_STORE_PASSWORD = config('SSLCOMMERZ_STORE_PASSWORD')
SSLCOMMERZ_IS_SANDBOX = config('SSLCOMMERZ_IS_SANDBOX', default=True, cast=bool)

#----------------- Email send _______________________________________
#EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default=f'Wearify <{EMAIL_HOST_USER}>')


SPECTACULAR_SETTINGS = {
    'TITLE': 'Wearify API',
    'DESCRIPTION': 'E-commerce API for Wearify — clothing store built with Django REST Framework',
    'VERSION': '1.0.0',
}

#......................Loggin and Monitoring....................................................
# Make sure the logs/ directory exists before the FileHandler tries to write
# to it — a fresh clone (or Render's build) won't have this folder yet, and
# Django would crash on startup without it.
os.makedirs(BASE_DIR / 'logs', exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'error.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'shop': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

#.......................celery and redis.........................................
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Dhaka'

#................Vite default port............................
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS', default='http://localhost:5173',
    cast=lambda v: [s.strip() for s in v.split(',')]
)

CORS_ALLOW_CREDENTIALS = True
