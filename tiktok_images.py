#!/usr/bin/env python3
"""Download HD images (photo mode / slideshow) from a TikTok post.

Usage: python tiktok_images.py <tiktok_url> [output_dir]

Strategy:
  1. yt-dlp (github.com/yt-dlp/yt-dlp) resolves the URL & metadata.
     yt-dlp only downloads videos/audio, so for photo posts we read the
     raw API data it exposes, if any.
  2. Parse TikTok's web page JSON (imagePost.images[].imageURL.urlList).
  3. Fallback: the public tikwm.com API.
Only image files are saved -- no video, no audio.
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def http_get(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Referer": "https://www.tiktok.com/"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
        return (data, r.geturl()) if binary else (data.decode("utf-8", "replace"), r.geturl())


def from_ytdlp(url):
    try:
        import yt_dlp
    except ImportError:
        return []
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True,
                               "ignore_no_formats_error": True}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:  # photo posts are often "unsupported"
        print(f"[yt-dlp] {e}")
        return []
    urls = []
    for key in ("_api_data", "_raw"):
        raw = info.get(key) or {}
        for img in (raw.get("image_post_info") or {}).get("images", []):
            lst = (img.get("display_image") or {}).get("url_list") or []
            if lst:
                urls.append(lst[0])
    return urls


def from_webpage(url):
    try:
        html, final = http_get(url)
    except Exception as e:
        print(f"[web] {e}")
        return []
    m = re.search(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
        item = data["__DEFAULT_SCOPE__"]["webapp.video-detail"]["itemInfo"]["itemStruct"]
        imgs = item["imagePost"]["images"]
    except Exception as e:
        print(f"[web] no imagePost: {e}")
        return []
    out = []
    for img in imgs:
        lst = img["imageURL"]["urlList"]
        # prefer jpeg (non-webp) original
        lst = sorted(lst, key=lambda u: ".webp" in u)
        out.append(lst[0])
    return out


def from_tikwm(url):
    api = "https://www.tikwm.com/api/?hd=1&url=" + urllib.parse.quote(url, safe="")
    try:
        body, _ = http_get(api)
        data = json.loads(body).get("data") or {}
    except Exception as e:
        print(f"[tikwm] {e}")
        return []
    return data.get("images") or []


def main():
    url = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "images"
    os.makedirs(out_dir, exist_ok=True)

    images = []
    for name, fn in (("yt-dlp", from_ytdlp), ("web", from_webpage), ("tikwm", from_tikwm)):
        images = fn(url)
        print(f"[{name}] found {len(images)} image(s)")
        if images:
            break
    if not images:
        sys.exit("No images found -- is this really a photo post?")

    for i, img_url in enumerate(images, 1):
        data, _ = http_get(img_url, binary=True)
        ext = "webp" if data[8:12] == b"WEBP" else ("png" if data[:4] == b"\x89PNG" else "jpg")
        path = os.path.join(out_dir, f"image_{i:02d}.{ext}")
        with open(path, "wb") as f:
            f.write(data)
        print(f"saved {path} ({len(data)//1024} KB)")


if __name__ == "__main__":
    main()
