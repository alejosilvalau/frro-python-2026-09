import cv2
import sys
import os
from pathlib import Path
from PIL import Image
from PIL.ExifTags import TAGS


EXTS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp"}


def get_exif_datetime(path):
    try:
        img = Image.open(path)
        exif = img._getexif()
        if exif:
            for tag_id, val in exif.items():
                if TAGS.get(tag_id) == "DateTimeOriginal" or TAGS.get(tag_id) == "DateTime":
                    return str(val)
    except Exception:
        pass
    return None


def load_images(dir_path, max_images=50):
    dir_path = Path(dir_path)
    files = [f for f in dir_path.iterdir() if f.suffix.lower() in EXTS]

    if not files:
        print(f"No image files found in {dir_path}")
        sys.exit(1)

    print(f"Found {len(files)} images")

    imgs_with_meta = []
    for f in files:
        dt = get_exif_datetime(f)
        imgs_with_meta.append((dt or "9999", f))

    imgs_with_meta.sort(key=lambda x: x[0])

    if len(imgs_with_meta) > max_images:
        step = len(imgs_with_meta) / max_images
        sampled = []
        for i in range(max_images):
            idx = min(int(i * step), len(imgs_with_meta) - 1)
            sampled.append(imgs_with_meta[idx])
        imgs_with_meta = sampled
        print(f"Sampled down to {len(sampled)} images")

    frames = []
    for dt, f in imgs_with_meta:
        print(f"  {f.name}  ({dt})")
        img = cv2.imread(str(f))
        if img is not None:
            frames.append(img)

    print(f"Loaded {len(frames)} images")
    return frames


def resize_if_big(img, max_dim=2000):
    h, w = img.shape[:2]
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        new_w, new_h = int(w * scale), int(h * scale)
        return cv2.resize(img, (new_w, new_h))
    return img


def create_panorama(images):
    if len(images) < 2:
        print("Need >=2 images")
        return images[0] if images else None

    images = [resize_if_big(img) for img in images]

    stitcher = cv2.Stitcher.create(cv2.Stitcher_PANORAMA)
    status, panorama = stitcher.stitch(images)

    if status == cv2.Stitcher_OK:
        return panorama

    print(f"Stitcher status {status}, trying subset...")
    for n in range(len(images) - 1, 1, -1):
        status, panorama = stitcher.stitch(images[:n])
        if status == cv2.Stitcher_OK:
            print(f"Stitched first {n} images")
            if n < len(images):
                rest = images[n:]
                rest.insert(0, panorama)
                status2, panorama = stitcher.stitch(rest)
                if status2 == cv2.Stitcher_OK:
                    return panorama
            return panorama

    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python panorama.py <image_dir>")
        sys.exit(1)

    dir_path = sys.argv[1]

    if not os.path.isdir(dir_path):
        print(f"Not a directory: {dir_path}")
        sys.exit(1)

    images = load_images(dir_path)
    if not images:
        print("No images loaded")
        sys.exit(1)

    panorama = create_panorama(images)
    if panorama is not None:
        output_path = Path(dir_path).name + "_panorama.jpg"
        cv2.imwrite(output_path, panorama)
        h, w = panorama.shape[:2]
        print(f"Panorama saved: {output_path} ({w}x{h})")
    else:
        print("Panorama stitching failed")


if __name__ == "__main__":
    main()
