import cloudinary.uploader

def upload_image(file, folder="general"):
    result = cloudinary.uploader.upload(
        file,
        folder=folder,
        resource_type="image",
        transformation=[
            {"quality": "auto", "fetch_format": "auto"}
        ]
    )
    return result.get("secure_url")

def upload_video(file, folder="videos"):
    result = cloudinary.uploader.upload(
        file,
        folder=folder,
        resource_type="video",
    )
    return {
        "url": result.get("secure_url"),
        "thumbnail": result.get("secure_url").replace(
            "/upload/", "/upload/so_0,f_jpg/"
        )
    }

def delete_file(public_id):
    cloudinary.uploader.destroy(public_id)


def upload_audio(file, folder="voice_notes"):
    """كلاودينري بيتعامل مع ملفات الصوت كـ resource_type='video'"""
    result = cloudinary.uploader.upload(
        file,
        folder=folder,
        resource_type="video",
    )
    return {
        "url": result.get("secure_url"),
        "duration": result.get("duration"),
    }


def upload_raw(file, folder="files"):
    """لأي نوع ملف عام (pdf, docx, zip...الخ)"""
    result = cloudinary.uploader.upload(
        file,
        folder=folder,
        resource_type="raw",
    )
    return result.get("secure_url")

import re

def extract_public_id(url, folder_hint=None):
    """
    بيستخرج الـ public_id من Cloudinary secure_url عشان نقدر نمسح الملف.
    مثال: https://res.cloudinary.com/xxx/image/upload/v123456/customer_photos/abc-def.jpg
    → public_id = customer_photos/abc-def
    """
    if not url:
        return None
    # شيل الجزء اللي قبل /upload/
    match = re.search(r'/upload/(?:v\d+/)?(.+)\.\w+$', url)
    if not match:
        return None
    return match.group(1)


def delete_file(public_id, resource_type="image"):
    if not public_id:
        return
    try:
        cloudinary.uploader.destroy(public_id, resource_type=resource_type)
    except Exception as e:
        print(f"[Cloudinary] Failed to delete {public_id}: {e}")