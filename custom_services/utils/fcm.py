"""
ملف جديد: utils/fcm.py

بيتولى الاتصال بـ Firebase Admin SDK وإرسال push notifications،
وبيرجع أي توكنات بقت غير صالحة عشان نحذفها من الداتابيز.
"""

import json
import os
import logging

import firebase_admin
from firebase_admin import credentials, messaging

logger = logging.getLogger(__name__)


def _init_firebase_app():
    """
    بيتنفذ مرة واحدة بس (firebase_admin بيمنع تكرار init).
    بيقرا الـ credentials من environment variable مش من ملف،
    عشان مفيش سر مكتوب في الكود أو في الريبو.
    """
    if firebase_admin._apps:
        return

    cred_json = os.environ.get('FIREBASE_CREDENTIALS_JSON')
    if not cred_json:
        logger.error('FIREBASE_CREDENTIALS_JSON غير موجود في environment variables — الـ push هيفضل معطل.')
        return

    try:
        cred_dict = json.loads(cred_json)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f'فشل تحميل Firebase credentials: {e}')


def send_push_to_tokens(tokens, title, body, data=None):
    """
    بيبعت push notification لقائمة توكنات (جهاز واحد أو أكتر لنفس اليوزر أو مستخدمين مختلفين).

    tokens: list[str]
    title, body: str — نص الإشعار
    data: dict — بيانات إضافية تتبعت مع الإشعار (request_id, event, notification_id...)
          كل القيم لازم تكون string (قيود FCM على data payload)

    بترجع dict: {'success_count': int, 'invalid_tokens': list[str]}
    invalid_tokens لازم تُحذف من جدول DeviceToken بعد الاستدعاء.
    """
    _init_firebase_app()

    if not firebase_admin._apps or not tokens:
        return {'success_count': 0, 'invalid_tokens': []}

    # FCM بيشترط كل قيم data تكون string
    string_data = {k: str(v) for k, v in (data or {}).items()}

    success_count = 0
    invalid_tokens = []

    for token in tokens:
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=string_data,
            token=token,
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    channel_id='default_channel',  # لازم يطابق الـ channel المعرف في كود الموبايل
                ),
            ),
            apns=messaging.APNSConfig(
                headers={'apns-priority': '10'},
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(sound='default', content_available=True),
                ),
            ),
        )
        try:
            messaging.send(message)
            success_count += 1
        except messaging.UnregisteredError:
            # التطبيق اتشال أو التوكن قديم — نحذفه عندنا
            invalid_tokens.append(token)
        except Exception as e:
            # أي خطأ تاني (نت، quota...) — نسجله بس مش نحذف التوكن
            logger.warning(f'فشل إرسال push لتوكن {token[:15]}...: {e}')

    return {'success_count': success_count, 'invalid_tokens': invalid_tokens}