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