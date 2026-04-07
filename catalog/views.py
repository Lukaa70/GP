import os
import hashlib
import requests
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.db.models import Count
from django.core.files.base import ContentFile
from .models import Actress, Photo, StagedActress, StagedPhoto, FavoriteScene, ScrapingTask
import json
from django.http import HttpResponse
from .scrapers.iafd import get_actress_data, scrape_profile_by_url
from .scrapers.pornpics import scrape_actress_photos, get_gallery_urls, scrape_gallery_photos


# ── Scraper test (single name via URL) ───────────────────────────────────────

def test_scraper(request):
    name = request.GET.get("name", "").strip()
    if not name:
        return HttpResponse("Provide ?name=Actress+Name", status=400)

    data, _ = get_actress_data(name)   # unpack tuple; discard search results

    if not data:
        return HttpResponse(f"No results found for '{name}'", status=404)

    actress, created = Actress.objects.update_or_create(
        name=data["name"],
        defaults={
            "date_of_birth":      data.get("date_of_birth"),
            "birth_country":      data.get("birth_country") or "",
            "nationality":        data.get("nationality") or "",
            "height_cm":          data.get("height_cm"),
            "weight_kg":          data.get("weight_kg"),
            "years_active_start": data.get("years_active_start"),
            "years_active_end":   data.get("years_active_end"),
        }
    )

    action = "Created" if created else "Updated"
    return HttpResponse(
        f"{action}: {actress.name} (id={actress.id})\n\n{data}",
        content_type="text/plain",
    )


# ── Bulk import (IAFD) ────────────────────────────────────────────────────────

def bulk_import(request):
    if request.method == "GET":
        return render(request, "catalog/bulk_import.html")
    # POST is now handled client-side via import_process_one — redirect to review
    return redirect("staged_review")


@require_POST
def import_process_one(request):
    """
    Process a single actress name for the AJAX-driven bulk import.
    Called once per name from the frontend, returns JSON.
    """
    from django.http import JsonResponse
    name = request.POST.get("name", "").strip()
    if not name:
        return JsonResponse({"ok": False, "error": "No name provided"})

    # Duplicate check — warn if already in the approved collection
    existing = Actress.objects.filter(name__iexact=name).first()
    if existing:
        return JsonResponse({
            "ok":        False,
            "duplicate": True,
            "existing_id": existing.id,
            "error":     f"Already in collection as '{existing.name}' (id={existing.id})",
        })

    try:
        data, search_results = get_actress_data(name)
        if data:
            # Also check by scraped name (may differ from search query)
            scraped_name = data.get("name") or ""
            existing_by_scraped = Actress.objects.filter(name__iexact=scraped_name).first() if scraped_name else None
            if existing_by_scraped:
                return JsonResponse({
                    "ok":          False,
                    "duplicate":   True,
                    "existing_id": existing_by_scraped.id,
                    "error":       f"Already in collection as '{existing_by_scraped.name}' (matched scraped name)",
                })

            staged = StagedActress.objects.create(
                query               = name,
                status              = StagedActress.Status.PENDING,
                iafd_url            = search_results[0]["url"] if search_results else "",
                iafd_search_results = search_results,
                name                = scraped_name,
                date_of_birth       = data.get("date_of_birth"),
                birth_country       = data.get("birth_country") or "",
                height_cm           = data.get("height_cm"),
                weight_kg           = data.get("weight_kg"),
                years_active_start  = data.get("years_active_start"),
                years_active_end    = data.get("years_active_end"),
            )
            if data.get("nationality"):
                Actress.objects.filter(name=scraped_name).update(nationality=data.get("nationality"))
            return JsonResponse({
                "ok":           True,
                "staged_id":    staged.id,
                "scraped_name": scraped_name,
                "alternatives": len(search_results) - 1,
            })
        else:
            StagedActress.objects.create(
                query               = name,
                status              = StagedActress.Status.ERROR,
                iafd_search_results = search_results,
                error               = "No results found on IAFD.",
            )
            return JsonResponse({"ok": False, "error": "No results found on IAFD"})

    except Exception as exc:
        StagedActress.objects.create(
            query  = name,
            status = StagedActress.Status.ERROR,
            error  = str(exc),
        )
        return JsonResponse({"ok": False, "error": str(exc)})


# ── Staged review (IAFD) ──────────────────────────────────────────────────────

def staged_review(request):
    pending  = StagedActress.objects.filter(status=StagedActress.Status.PENDING)
    errors   = StagedActress.objects.filter(status=StagedActress.Status.ERROR)
    approved = StagedActress.objects.filter(status=StagedActress.Status.APPROVED)
    rejected = StagedActress.objects.filter(status=StagedActress.Status.REJECTED)

    approved_names     = [s.name for s in approved]
    approved_actresses = Actress.objects.filter(name__in=approved_names)

    return render(request, "catalog/staged_review.html", {
        "pending":            pending,
        "errors":             errors,
        "approved":           approved,
        "rejected":           rejected,
        "approved_actresses": approved_actresses,
    })


# ── Approve / reject staged actress ──────────────────────────────────────────

@require_POST
def approve_staged(request, staged_id):
    staged = get_object_or_404(StagedActress, id=staged_id)

    Actress.objects.update_or_create(
        name=staged.name,
        defaults={
            "date_of_birth":      staged.date_of_birth,
            "birth_country":      staged.birth_country or "",
            "height_cm":          staged.height_cm,
            "weight_kg":          staged.weight_kg,
            "years_active_start": staged.years_active_start,
            "years_active_end":   staged.years_active_end,
        }
    )

    staged.status = StagedActress.Status.APPROVED
    staged.save()
    return redirect("staged_review")


@require_POST
def reject_staged(request, staged_id):
    staged = get_object_or_404(StagedActress, id=staged_id)
    staged.status = StagedActress.Status.REJECTED
    staged.save()
    return redirect("staged_review")


@require_POST
def clear_staged_errors(request):
    """Delete all StagedActress records with status=error."""
    StagedActress.objects.filter(status=StagedActress.Status.ERROR).delete()
    return redirect("staged_review")


# ── Repick IAFD result ────────────────────────────────────────────────────────

@require_POST
def repick_iafd_result(request, staged_id):
    """
    The user chose a different result from the stored search alternatives.
    Re-scrape that profile URL and update the staged record.
    """
    staged       = get_object_or_404(StagedActress, id=staged_id)
    selected_url = request.POST.get("iafd_url", "").strip()

    if not selected_url:
        return redirect("staged_review")

    data = scrape_profile_by_url(selected_url)
    if not data:
        return redirect("staged_review")

    staged.iafd_url            = selected_url
    staged.name                = data.get("name") or staged.name
    staged.date_of_birth       = data.get("date_of_birth")
    staged.birth_country       = data.get("birth_country") or ""
    staged.height_cm           = data.get("height_cm")
    staged.weight_kg           = data.get("weight_kg")
    staged.years_active_start  = data.get("years_active_start")
    staged.years_active_end    = data.get("years_active_end")
    staged.status              = StagedActress.Status.PENDING
    staged.save()

    return redirect("staged_review")


# ── Photo scraping ────────────────────────────────────────────────────────────

@require_POST
def scrape_photos_for_actress(request, actress_id):
    actress = get_object_or_404(Actress, id=actress_id)

    # Allow overriding the search name (e.g. when pornpics uses an alias)
    search_name = request.POST.get("search_name", "").strip() or actress.name

    # Configurable scrape depth with sensible caps
    try:
        max_galleries = max(1, min(30, int(request.POST.get("max_galleries", 10))))
    except (ValueError, TypeError):
        max_galleries = 10

    try:
        photos_per_gallery = max(1, min(20, int(request.POST.get("photos_per_gallery", 5))))
    except (ValueError, TypeError):
        photos_per_gallery = 5

    # Clear previously staged pending photos to avoid duplicates on re-scrape
    actress.staged_photos.filter(status=StagedPhoto.Status.PENDING).delete()

    photo_dicts = scrape_actress_photos(search_name, max_galleries, photos_per_gallery)

    headers = {
        "Referer":    "https://www.pornpics.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    for photo in photo_dicts:
        try:
            resp = requests.get(photo["source_url_460"], headers=headers, timeout=15)
            resp.raise_for_status()

            content   = resp.content
            img_hash  = hashlib.md5(content).hexdigest()
            is_dup    = actress.photos.filter(image_hash=img_hash).exists()

            filename = os.path.basename(photo["source_url_460"].split("?")[0])
            staged   = StagedPhoto(
                actress         = actress,
                source_url_460  = photo["source_url_460"],
                source_url_1280 = photo.get("source_url_1280", ""),
                gallery_title   = photo.get("gallery_title", ""),
                gallery_url     = photo.get("gallery_url", ""),
                status          = StagedPhoto.Status.PENDING,
                image_hash      = img_hash,
                is_duplicate    = is_dup,
            )
            staged.local_file.save(filename, ContentFile(content), save=True)

        except Exception:
            continue

    return redirect("photo_review", actress_id=actress_id)


# ── Two-stage AJAX photo scraping (with progress) ────────────────────────────

@require_POST
def scrape_photos_start(request, actress_id):
    """
    Stage 1: runs Playwright on the search page only, returns list of gallery URLs.
    Fast (~5s). Frontend then calls scrape_gallery_batch once per gallery.
    """
    from django.http import JsonResponse
    actress     = get_object_or_404(Actress, id=actress_id)
    search_name = request.POST.get("search_name", "").strip() or actress.name
    try:
        max_galleries = max(1, min(30, int(request.POST.get("max_galleries", 10))))
    except (ValueError, TypeError):
        max_galleries = 10

    # Clear pending staged photos so re-scrape starts fresh
    actress.staged_photos.filter(status=StagedPhoto.Status.PENDING).delete()

    try:
        galleries = get_gallery_urls(search_name, max_galleries)
        return JsonResponse({"ok": True, "galleries": galleries, "actress_id": actress_id})
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)})


@require_POST
def scrape_gallery_batch(request, actress_id):
    """
    Stage 2: scrape one gallery and download its photos.
    Called once per gallery from the frontend loop.
    """
    from django.http import JsonResponse
    actress       = get_object_or_404(Actress, id=actress_id)
    gallery_url   = request.POST.get("gallery_url", "").strip()
    gallery_title = request.POST.get("gallery_title", "").strip()
    try:
        photos_per_gallery = max(1, min(20, int(request.POST.get("photos_per_gallery", 5))))
    except (ValueError, TypeError):
        photos_per_gallery = 5

    if not gallery_url:
        return JsonResponse({"ok": False, "error": "No gallery URL"})

    headers = {
        "Referer":    "https://www.pornpics.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    try:
        photo_dicts = scrape_gallery_photos(gallery_url, gallery_title, photos_per_gallery)
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)})

    added = 0
    for photo in photo_dicts:
        try:
            resp = requests.get(photo["source_url_460"], headers=headers, timeout=15)
            resp.raise_for_status()
            content  = resp.content
            img_hash = hashlib.md5(content).hexdigest()
            is_dup   = actress.photos.filter(image_hash=img_hash).exists()
            filename = os.path.basename(photo["source_url_460"].split("?")[0])
            staged   = StagedPhoto(
                actress         = actress,
                source_url_460  = photo["source_url_460"],
                source_url_1280 = photo.get("source_url_1280", ""),
                gallery_title   = gallery_title,
                gallery_url     = gallery_url,
                status          = StagedPhoto.Status.PENDING,
                image_hash      = img_hash,
                is_duplicate    = is_dup,
            )
            staged.local_file.save(filename, ContentFile(content), save=True)
            added += 1
        except Exception:
            continue

    return JsonResponse({"ok": True, "added": added, "gallery_url": gallery_url})


# ── Scrape ALL photos from one specific gallery ───────────────────────────────

@require_POST
def scrape_full_album(request, actress_id):
    """
    Scrape every photo from a single gallery URL — no per-gallery limit.
    Called from the photo review page when the user clicks "Get all from album".
    """
    from django.http import JsonResponse
    actress       = get_object_or_404(Actress, id=actress_id)
    gallery_url   = request.POST.get("gallery_url", "").strip()
    gallery_title = request.POST.get("gallery_title", "").strip()

    if not gallery_url:
        return JsonResponse({"ok": False, "error": "No gallery URL"})

    headers = {
        "Referer":    "https://www.pornpics.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    try:
        # No max_photos limit — get everything
        photo_dicts = scrape_gallery_photos(gallery_url, gallery_title, max_photos=None)
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)})

    added = 0
    for photo in photo_dicts:
        # Skip if already staged for this actress
        if StagedPhoto.objects.filter(actress=actress, source_url_460=photo["source_url_460"]).exists():
            continue
        try:
            resp = requests.get(photo["source_url_460"], headers=headers, timeout=15)
            resp.raise_for_status()
            content  = resp.content
            img_hash = hashlib.md5(content).hexdigest()
            is_dup   = actress.photos.filter(image_hash=img_hash).exists()
            filename = os.path.basename(photo["source_url_460"].split("?")[0])
            staged   = StagedPhoto(
                actress         = actress,
                source_url_460  = photo["source_url_460"],
                source_url_1280 = photo.get("source_url_1280", ""),
                gallery_title   = gallery_title,
                gallery_url     = gallery_url,
                status          = StagedPhoto.Status.PENDING,
                image_hash      = img_hash,
                is_duplicate    = is_dup,
            )
            staged.local_file.save(filename, ContentFile(content), save=True)
            added += 1
        except Exception:
            continue

    return JsonResponse({"ok": True, "added": added})


# ── Photo review ──────────────────────────────────────────────────────────────

def photo_review(request, actress_id):
    actress  = get_object_or_404(Actress, id=actress_id)
    pending  = actress.staged_photos.filter(status=StagedPhoto.Status.PENDING)
    approved = actress.staged_photos.filter(status=StagedPhoto.Status.APPROVED)
    rejected = actress.staged_photos.filter(status=StagedPhoto.Status.REJECTED)

    galleries = {}
    for photo in pending:
        key = photo.gallery_url or "unknown"
        if key not in galleries:
            galleries[key] = {
                "title":  photo.gallery_title or key,
                "url":    photo.gallery_url,
                "photos": [],
            }
        galleries[key]["photos"].append(photo)

    return render(request, "catalog/photo_review.html", {
        "actress":       actress,
        "galleries":     galleries.values(),
        "approved":      approved,
        "rejected":      rejected,
        "total_pending": pending.count(),
    })


# ── Approve / reject single staged photo ─────────────────────────────────────

@require_POST
def approve_photo(request, staged_photo_id):
    staged  = get_object_or_404(StagedPhoto, id=staged_photo_id)
    actress = staged.actress

    # Duplicate check — skip if this exact image is already in the collection
    if staged.image_hash and actress.photos.filter(image_hash=staged.image_hash).exists():
        staged.status = StagedPhoto.Status.REJECTED
        staged.save()
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            from django.http import JsonResponse
            return JsonResponse({"ok": False, "reason": "duplicate"})
        return redirect("photo_review", actress_id=actress.id)

    photo = Photo(
        actress         = actress,
        caption         = staged.gallery_title,
        source_url_1280 = staged.source_url_1280,
        image_hash      = staged.image_hash,
    )
    with staged.local_file.open("rb") as f:
        content  = f.read()
        filename = os.path.basename(staged.local_file.name)
        # Store dimensions
        try:
            from PIL import Image as PILImage
            import io
            img = PILImage.open(io.BytesIO(content))
            photo.width, photo.height = img.width, img.height
        except Exception:
            pass
        photo.image.save(filename, ContentFile(content), save=True)

    staged.status = StagedPhoto.Status.APPROVED
    staged.save()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        from django.http import JsonResponse
        return JsonResponse({"ok": True})
    return redirect("photo_review", actress_id=actress.id)


@require_POST
def reject_photo(request, staged_photo_id):
    staged = get_object_or_404(StagedPhoto, id=staged_photo_id)

    if staged.local_file:
        staged.local_file.delete(save=False)

    staged.status = StagedPhoto.Status.REJECTED
    staged.save()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        from django.http import JsonResponse
        return JsonResponse({"ok": True})
    return redirect("photo_review", actress_id=staged.actress.id)


# ── Reject all photos in a gallery at once ────────────────────────────────────

@require_POST
def reject_gallery_photos(request, actress_id):
    """
    Skip every pending photo in a gallery in one click.
    The form sends all photo IDs as a list of hidden inputs.
    """
    actress   = get_object_or_404(Actress, id=actress_id)
    photo_ids = request.POST.getlist("photo_ids")

    staged_photos = StagedPhoto.objects.filter(
        id__in=photo_ids,
        actress=actress,
        status=StagedPhoto.Status.PENDING,
    )

    for sp in staged_photos:
        if sp.local_file:
            sp.local_file.delete(save=False)
        sp.status = StagedPhoto.Status.REJECTED
        sp.save()

    return redirect("photo_review", actress_id=actress_id)


# ── Upgrade photo to 1280px ───────────────────────────────────────────────────

@require_POST
def upgrade_photo(request, photo_id):
    from django.http import JsonResponse
    photo = get_object_or_404(Photo, id=photo_id)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if not photo.source_url_1280:
        if is_ajax:
            return JsonResponse({"ok": False, "reason": "no_url"})
        return redirect("actress_detail", id=photo.actress.id)

    headers = {
        "Referer":    "https://www.pornpics.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    try:
        resp = requests.get(photo.source_url_1280, headers=headers, timeout=20)
        resp.raise_for_status()

        content  = resp.content
        old_name = os.path.basename(photo.image.name)
        name_base, ext = os.path.splitext(old_name)
        hd_name  = f"{name_base}_hd{ext}"
        photo.image.delete(save=False)
        photo.image.save(hd_name, ContentFile(content), save=False)
        photo.source_url_1280 = ""
        photo.is_hd           = True
        photo.image_hash      = hashlib.md5(content).hexdigest()
        photo.save()

        if is_ajax:
            return JsonResponse({"ok": True, "new_url": photo.image.url, "photo_id": photo_id})

    except Exception as e:
        if is_ajax:
            return JsonResponse({"ok": False, "reason": str(e)})

    return redirect("actress_detail", id=photo.actress.id)


# ── Bulk AJAX: staged photo approve / reject ──────────────────────────────────

@require_POST
def bulk_approve_staged_photos(request):
    """Approve multiple staged photos in one call. Returns JSON."""
    from django.http import JsonResponse
    photo_ids     = request.POST.getlist("photo_ids[]")
    approved      = 0
    skipped_dupes = 0

    for pk in photo_ids:
        try:
            staged  = StagedPhoto.objects.get(id=pk, status=StagedPhoto.Status.PENDING)
            actress = staged.actress

            # Duplicate check
            if staged.image_hash and actress.photos.filter(image_hash=staged.image_hash).exists():
                staged.status = StagedPhoto.Status.REJECTED
                staged.save()
                skipped_dupes += 1
                continue

            photo = Photo(
                actress         = actress,
                caption         = staged.gallery_title,
                source_url_1280 = staged.source_url_1280,
                image_hash      = staged.image_hash,
            )
            with staged.local_file.open("rb") as f:
                filename = os.path.basename(staged.local_file.name)
                photo.image.save(filename, ContentFile(f.read()), save=True)

            staged.status = StagedPhoto.Status.APPROVED
            staged.save()
            approved += 1
        except Exception:
            continue

    return JsonResponse({"ok": True, "approved": approved, "skipped_dupes": skipped_dupes})


@require_POST
def bulk_reject_staged_photos(request):
    """Reject multiple staged photos in one call. Returns JSON."""
    from django.http import JsonResponse
    photo_ids = request.POST.getlist("photo_ids[]")
    processed = 0

    staged_photos = StagedPhoto.objects.filter(
        id__in=photo_ids,
        status=StagedPhoto.Status.PENDING,
    )
    for sp in staged_photos:
        if sp.local_file:
            sp.local_file.delete(save=False)
        sp.status = StagedPhoto.Status.REJECTED
        sp.save()
        processed += 1

    return JsonResponse({"ok": True, "processed": processed})


# ── Bulk AJAX: actress photo delete / upgrade ─────────────────────────────────

@require_POST
def bulk_delete_photos(request):
    """Delete multiple approved photos. Returns JSON."""
    from django.http import JsonResponse
    photo_ids = request.POST.getlist("photo_ids[]")
    processed = 0

    for pk in photo_ids:
        try:
            photo = Photo.objects.get(id=pk)
            photo.image.delete(save=False)
            photo.delete()
            processed += 1
        except Exception:
            continue

    return JsonResponse({"ok": True, "processed": processed})


@require_POST
def bulk_upgrade_photos(request):
    """Upgrade multiple photos to 1280px. Returns JSON with per-photo results."""
    from django.http import JsonResponse
    photo_ids = request.POST.getlist("photo_ids[]")
    upgraded  = []
    failed    = []

    headers = {
        "Referer":    "https://www.pornpics.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    for pk in photo_ids:
        try:
            photo = Photo.objects.get(id=pk)
            if not photo.source_url_1280:
                failed.append(pk)
                continue

            resp = requests.get(photo.source_url_1280, headers=headers, timeout=20)
            resp.raise_for_status()

            content   = resp.content
            name_base, ext = os.path.splitext(os.path.basename(photo.image.name))
            hd_name   = f"{name_base}_hd{ext}"
            photo.image.delete(save=False)
            photo.image.save(hd_name, ContentFile(content), save=False)
            photo.source_url_1280 = ""
            photo.is_hd           = True
            photo.image_hash      = hashlib.md5(content).hexdigest()
            photo.save()
            upgraded.append(pk)
        except Exception:
            failed.append(pk)

    return JsonResponse({"ok": True, "upgraded": upgraded, "failed": failed})


@require_POST
def update_actress_info(request, actress_id):
    """AJAX — update actress bio fields from the inline edit form on the detail page."""
    from django.http import JsonResponse
    from datetime import datetime as dt
    actress = get_object_or_404(Actress, id=actress_id)

    actress.name             = request.POST.get("name", "").strip() or actress.name
    actress.birth_country    = request.POST.get("birth_country", "").strip()
    actress.nationality      = request.POST.get("nationality", "").strip()
    actress.official_website = request.POST.get("official_website", "").strip()
    actress.onlyfans_url     = request.POST.get("onlyfans_url", "").strip()
    actress.twitter_url      = request.POST.get("twitter_url", "").strip()
    actress.instagram_url    = request.POST.get("instagram_url", "").strip()
    actress.notes            = request.POST.get("notes", "").strip()

    dob = request.POST.get("date_of_birth", "").strip()
    try:
        actress.date_of_birth = dt.strptime(dob, "%Y-%m-%d").date() if dob else None
    except ValueError:
        pass

    for field in ["height_cm", "weight_kg", "years_active_start", "years_active_end"]:
        val = request.POST.get(field, "").strip()
        setattr(actress, field, int(val) if val.isdigit() else None)

    actress.save()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "name": actress.name})
    return redirect("actress_detail", id=actress_id)


@require_POST
def refresh_actress_iafd(request, actress_id):
    """Re-scrape IAFD for this actress and update all bio fields including nationality."""
    from django.http import JsonResponse
    actress = get_object_or_404(Actress, id=actress_id)

    try:
        data, _ = get_actress_data(actress.name)
        if not data:
            return JsonResponse({"ok": False, "error": "No results found on IAFD"})

        actress.name               = data.get("name")               or actress.name
        actress.date_of_birth      = data.get("date_of_birth")      or actress.date_of_birth
        actress.birth_country      = data.get("birth_country")      or actress.birth_country
        actress.nationality        = data.get("nationality")        or actress.nationality
        actress.height_cm          = data.get("height_cm")          or actress.height_cm
        actress.weight_kg          = data.get("weight_kg")          or actress.weight_kg
        actress.years_active_start = data.get("years_active_start") or actress.years_active_start
        actress.years_active_end   = data.get("years_active_end")   or actress.years_active_end
        actress.save()

        return JsonResponse({
            "ok":   True,
            "name": actress.name,
            "data": {
                "birth_country":      actress.birth_country,
                "nationality":        actress.nationality,
                "date_of_birth":      str(actress.date_of_birth) if actress.date_of_birth else "",
                "height_cm":          actress.height_cm,
                "weight_kg":          actress.weight_kg,
                "years_active_start": actress.years_active_start,
                "years_active_end":   actress.years_active_end,
            }
        })

    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)})


@require_POST
def bulk_refresh_all_iafd(request):
    """
    Re-scrape IAFD for every actress in the DB, one at a time.
    Called via AJAX from the collection page with an actress_id each call.
    Returns JSON with updated fields for that one actress.
    """
    from django.http import JsonResponse
    actress_id = request.POST.get("actress_id")
    if not actress_id:
        # Return full list of IDs to process on first call
        ids = list(Actress.objects.values_list("id", flat=True))
        return JsonResponse({"ok": True, "ids": ids, "total": len(ids)})

    actress = get_object_or_404(Actress, id=actress_id)
    try:
        data, _ = get_actress_data(actress.name)
        if data:
            actress.date_of_birth      = data.get("date_of_birth")      or actress.date_of_birth
            actress.birth_country      = data.get("birth_country")      or actress.birth_country
            actress.nationality        = data.get("nationality")        or actress.nationality
            actress.height_cm          = data.get("height_cm")          or actress.height_cm
            actress.weight_kg          = data.get("weight_kg")          or actress.weight_kg
            actress.years_active_start = data.get("years_active_start") or actress.years_active_start
            actress.years_active_end   = data.get("years_active_end")   or actress.years_active_end
            actress.save()
        return JsonResponse({"ok": True, "actress_id": actress_id, "name": actress.name,
                             "nationality": actress.nationality})
    except Exception as exc:
        return JsonResponse({"ok": False, "actress_id": actress_id, "name": actress.name,
                             "error": str(exc)})


@require_POST
def set_actress_rating(request, actress_id):
    """AJAX — set star rating (1-5) on an actress. POST rating=N or rating=0 to clear."""
    from django.http import JsonResponse
    actress = get_object_or_404(Actress, id=actress_id)
    try:
        rating = int(request.POST.get("rating", 0))
        actress.rating = rating if 1 <= rating <= 5 else None
        actress.save(update_fields=["rating"])
        return JsonResponse({"ok": True, "rating": actress.rating})
    except (ValueError, TypeError) as e:
        return JsonResponse({"ok": False, "error": str(e)})


@require_POST
def add_scene(request, actress_id):
    """Add a FavoriteScene entry for an actress."""
    from django.http import JsonResponse
    actress = get_object_or_404(Actress, id=actress_id)
    title       = request.POST.get("title", "").strip()
    description = request.POST.get("description", "").strip()
    scene_link  = request.POST.get("scene_link", "").strip()
    rating_raw  = request.POST.get("rating", "")

    if not title and not description:
        return JsonResponse({"ok": False, "error": "Title or description required"})

    try:
        rating = int(rating_raw) if rating_raw else None
    except ValueError:
        rating = None

    scene = FavoriteScene.objects.create(
        actress     = actress,
        title       = title,
        description = description,
        scene_link  = scene_link,
        rating      = rating,
    )
    return JsonResponse({
        "ok":          True,
        "id":          scene.id,
        "title":       scene.title,
        "description": scene.description,
        "scene_link":  scene.scene_link,
        "rating":      scene.rating,
    })


@require_POST
def delete_scene(request, scene_id):
    """Delete a FavoriteScene entry."""
    from django.http import JsonResponse
    scene = get_object_or_404(FavoriteScene, id=scene_id)
    scene.delete()
    return JsonResponse({"ok": True})


def export_backup(request):
    """
    Generate and stream a ZIP file containing:
    - data/actresses.csv  (all actress fields)
    - data/scenes.csv     (all favourite scenes)
    - photos/<actress_name>/<filename>  (all approved photos)
    """
    import csv
    import zipfile
    import io
    from django.http import StreamingHttpResponse

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:

        # ── actresses.csv ──────────────────────────────────────────────
        csv_buf = io.StringIO()
        writer  = csv.writer(csv_buf)
        writer.writerow([
            'id','name','nationality','birth_country','date_of_birth',
            'height_cm','weight_kg','years_active_start','years_active_end',
            'rating','official_website','onlyfans_url','twitter_url',
            'instagram_url','notes','photo_count',
        ])
        for a in Actress.objects.all().order_by('name'):
            writer.writerow([
                a.id, a.name, a.nationality, a.birth_country,
                a.date_of_birth or '', a.height_cm or '', a.weight_kg or '',
                a.years_active_start or '', a.years_active_end or '',
                a.rating or '', a.official_website, a.onlyfans_url,
                a.twitter_url, a.instagram_url, a.notes,
                a.photos.count(),
            ])
        zf.writestr('data/actresses.csv', csv_buf.getvalue())

        # ── scenes.csv ─────────────────────────────────────────────────
        csv_buf = io.StringIO()
        writer  = csv.writer(csv_buf)
        writer.writerow(['id','actress','title','description','scene_link','rating','added_at'])
        for s in FavoriteScene.objects.select_related('actress').order_by('actress__name'):
            writer.writerow([
                s.id, s.actress.name, s.title, s.description,
                s.scene_link, s.rating or '', s.added_at.strftime('%Y-%m-%d'),
            ])
        zf.writestr('data/scenes.csv', csv_buf.getvalue())

        # ── photos ─────────────────────────────────────────────────────
        for actress in Actress.objects.prefetch_related('photos').order_by('name'):
            safe_name = "".join(c if c.isalnum() or c in ' ._-' else '_' for c in actress.name)
            for photo in actress.photos.all():
                try:
                    with photo.image.open('rb') as f:
                        filename = os.path.basename(photo.image.name)
                        zf.writestr(f'photos/{safe_name}/{filename}', f.read())
                except Exception:
                    continue

    buf.seek(0)
    from datetime import date
    filename = f"actressdb_backup_{date.today().isoformat()}.zip"
    response = StreamingHttpResponse(
        buf,
        content_type='application/zip',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _run_in_thread(fn, *args, **kwargs):
    """Start fn(*args, **kwargs) in a daemon thread and return immediately."""
    import threading
    t = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
    t.start()
    return t


def _task_update(task_id, **kwargs):
    """Update a ScrapingTask row atomically — safe to call from threads."""
    from django.utils import timezone as tz
    updates = kwargs
    if kwargs.get('status') in ('done', 'error'):
        updates['finished_at'] = tz.now()
    ScrapingTask.objects.filter(id=task_id).update(**updates)


# ── Task status polling ───────────────────────────────────────────────────────

def task_status(request, task_id):
    from django.http import JsonResponse
    task = get_object_or_404(ScrapingTask, id=task_id)
    return JsonResponse({
        'id':       task.id,
        'status':   task.status,
        'pct':      task.pct,
        'message':  task.message,
        'label':    task.label,
        'error':    task.error,
        'actress_id': task.actress_id,
    })


def tasks_active(request):
    """Return all running/pending tasks — used to restore progress bars on page load."""
    from django.http import JsonResponse
    tasks = ScrapingTask.objects.filter(status__in=['pending', 'running']).order_by('-created_at')[:10]
    return JsonResponse({'tasks': [
        {'id': t.id, 'status': t.status, 'pct': t.pct, 'message': t.message,
         'label': t.label, 'actress_id': t.actress_id}
        for t in tasks
    ]})


# ── Background photo scraping ─────────────────────────────────────────────────

def _bg_photo_scrape(task_id, actress_id, search_name, max_galleries, photos_per_gallery):
    """Runs in a background thread. Scrapes photos and updates task progress."""
    from django.db import connection as db_conn
    db_conn.close_old_connections()

    try:
        actress = Actress.objects.get(id=actress_id)

        _task_update(task_id, status='running', message='Searching PornPics…')

        galleries = get_gallery_urls(search_name, max_galleries)
        _task_update(task_id, total=len(galleries), message=f'Found {len(galleries)} galleries')

        # Clear pending staged photos
        actress.staged_photos.filter(status=StagedPhoto.Status.PENDING).delete()

        headers = {
            "Referer":    "https://www.pornpics.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

        for i, gallery in enumerate(galleries):
            _task_update(task_id,
                         progress=i,
                         message=f'Gallery {i+1}/{len(galleries)}: {gallery.get("title","") or gallery["url"]}')

            try:
                photo_dicts = scrape_gallery_photos(
                    gallery['url'], gallery.get('title', ''), photos_per_gallery
                )
                for photo in photo_dicts:
                    try:
                        resp = requests.get(photo['source_url_460'], headers=headers, timeout=15)
                        resp.raise_for_status()
                        content  = resp.content
                        img_hash = hashlib.md5(content).hexdigest()
                        is_dup   = actress.photos.filter(image_hash=img_hash).exists()
                        filename = os.path.basename(photo['source_url_460'].split('?')[0])
                        staged   = StagedPhoto(
                            actress         = actress,
                            source_url_460  = photo['source_url_460'],
                            source_url_1280 = photo.get('source_url_1280', ''),
                            gallery_title   = gallery.get('title', ''),
                            gallery_url     = gallery['url'],
                            status          = StagedPhoto.Status.PENDING,
                            image_hash      = img_hash,
                            is_duplicate    = is_dup,
                        )
                        staged.local_file.save(filename, ContentFile(content), save=True)
                    except Exception:
                        continue
            except Exception:
                continue

        _task_update(task_id, status='done', progress=len(galleries),
                     message=f'Done — {actress.pending_staged_photos_count} photos ready for review')

    except Exception as exc:
        _task_update(task_id, status='error', error=str(exc), message='Scrape failed')

    finally:
        from django.db import connection as db_conn2
        db_conn2.close_old_connections()


@require_POST
def scrape_photos_bg(request, actress_id):
    """Start a background photo scrape and return the task ID immediately."""
    from django.http import JsonResponse
    actress     = get_object_or_404(Actress, id=actress_id)
    search_name = request.POST.get('search_name', '').strip() or actress.name
    try:
        max_galleries      = max(1, min(30, int(request.POST.get('max_galleries', 10))))
        photos_per_gallery = max(1, min(20, int(request.POST.get('photos_per_gallery', 5))))
        if request.POST.get('full_albums'):
            photos_per_gallery = 999
    except (ValueError, TypeError):
        max_galleries, photos_per_gallery = 10, 5

    task = ScrapingTask.objects.create(
        task_type = ScrapingTask.TaskType.PHOTOS_SCRAPE,
        actress   = actress,
        label     = f'Photos: {actress.name}',
        status    = ScrapingTask.Status.PENDING,
        message   = 'Starting…',
    )

    _run_in_thread(_bg_photo_scrape, task.id, actress_id,
                   search_name, max_galleries, photos_per_gallery)

    return JsonResponse({'ok': True, 'task_id': task.id, 'actress_id': actress_id})


# ── IAFD Rescrape UI ──────────────────────────────────────────────────────────

def rescrape_ui(request):
    """Page to select actresses and IAFD fields to rescrape."""
    actresses = Actress.objects.all().order_by('name')
    fields_choices = [
        ('nationality',        'Nationality'),
        ('birth_country',      'Birth country'),
        ('date_of_birth',      'Date of birth'),
        ('height_cm',          'Height'),
        ('weight_kg',          'Weight'),
        ('years_active_start', 'Active from'),
        ('years_active_end',   'Active to'),
    ]
    return render(request, 'catalog/rescrape.html', {
        'actresses':      actresses,
        'fields_choices': fields_choices,
    })


def _bg_iafd_rescrape(task_id, actress_ids, fields):
    """Runs in a background thread. Re-scrapes IAFD for each actress."""
    from django.db import connection as db_conn
    db_conn.close_old_connections()

    total = len(actress_ids)
    _task_update(task_id, status='running', total=total, message=f'Rescraping {total} actress{"es" if total != 1 else ""}…')

    for i, actress_id in enumerate(actress_ids):
        try:
            actress = Actress.objects.get(id=actress_id)
            _task_update(task_id, progress=i, message=f'{i+1}/{total}: {actress.name}')

            data, _ = get_actress_data(actress.name)
            if data:
                for field in fields:
                    new_val = data.get(field)
                    if new_val:
                        setattr(actress, field, new_val)
                actress.save()

        except Exception as exc:
            # Log but continue to next actress
            _task_update(task_id, message=f'{i+1}/{total}: error on {actress_id} — {exc}')
            continue

    _task_update(task_id, status='done', progress=total,
                 message=f'Done — {total} actress{"es" if total != 1 else ""} updated')

    from django.db import connection as db_conn2
    db_conn2.close_old_connections()


@require_POST
def rescrape_start(request):
    """Start a background IAFD rescrape for selected actresses and fields."""
    from django.http import JsonResponse

    actress_ids = request.POST.getlist('actress_ids[]')
    if not actress_ids:
        # "All" mode
        actress_ids = list(Actress.objects.values_list('id', flat=True))

    fields = request.POST.getlist('fields[]')
    allowed_fields = {
        'date_of_birth', 'birth_country', 'nationality',
        'height_cm', 'weight_kg', 'years_active_start', 'years_active_end',
    }
    fields = [f for f in fields if f in allowed_fields]
    if not fields:
        fields = list(allowed_fields)

    task = ScrapingTask.objects.create(
        task_type = ScrapingTask.TaskType.IAFD_BULK,
        label     = f'IAFD rescrape: {len(actress_ids)} actresses, fields: {", ".join(fields)}',
        status    = ScrapingTask.Status.PENDING,
        message   = 'Queued…',
    )

    _run_in_thread(_bg_iafd_rescrape, task.id, actress_ids, fields)

    return JsonResponse({'ok': True, 'task_id': task.id, 'total': len(actress_ids)})


# ── helpers ──────────────────────────────────────────────────────────────────

HEIGHT_BUCKETS = [
    ("<155",    0,   154),
    ("155–159", 155, 159),
    ("160–164", 160, 164),
    ("165–169", 165, 169),
    ("170–174", 170, 174),
    ("175+",    175, 999),
]

DECADE_CHOICES = [1960, 1970, 1980, 1990, 2000, 2010]


def _decade_distribution():
    labels, counts = [], []
    for start in DECADE_CHOICES:
        count = Actress.objects.filter(
            date_of_birth__year__gte=start,
            date_of_birth__year__lte=start + 9,
        ).count()
        labels.append(f"{start}s")
        counts.append(count)
    return labels, counts


def _height_distribution():
    labels, counts = [], []
    for label, lo, hi in HEIGHT_BUCKETS:
        count = Actress.objects.filter(
            height_cm__gte=lo,
            height_cm__lte=hi,
        ).count()
        labels.append(label)
        counts.append(count)
    return labels, counts


# ── List view ─────────────────────────────────────────────────────────────────

def actress_list(request):
    from django.core.paginator import Paginator

    actresses = Actress.objects.all()

    country    = request.GET.get('country', '').strip()
    decade     = request.GET.get('decade', '')
    height_min = request.GET.get('height_min', '')
    height_max = request.GET.get('height_max', '')
    name       = request.GET.get('name', '').strip()
    sort       = request.GET.get('sort', 'name')
    min_rating = request.GET.get('min_rating', '')

    if name:
        actresses = actresses.filter(name__icontains=name)
    if country:
        actresses = actresses.filter(birth_country__icontains=country)
    if decade:
        start_year = int(decade)
        actresses  = actresses.filter(
            date_of_birth__year__gte=start_year,
            date_of_birth__year__lte=start_year + 9,
        )
    if height_min:
        actresses = actresses.filter(height_cm__gte=int(height_min))
    if height_max:
        actresses = actresses.filter(height_cm__lte=int(height_max))
    if min_rating:
        actresses = actresses.filter(rating__gte=int(min_rating))

    sort_map = {
        'name':       'name',
        '-name':      '-name',
        'rating':     '-rating',
        'added':      '-id',
        'height':     '-height_cm',
    }
    actresses = actresses.order_by(sort_map.get(sort, 'name'))

    # Pagination — 24 per page
    paginator = Paginator(actresses, 24)
    page_num  = request.GET.get('page', 1)
    page_obj  = paginator.get_page(page_num)

    nationality_stats = (
        Actress.objects.exclude(nationality="")
        .values('nationality')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    decade_labels, decade_counts = _decade_distribution()
    height_labels, height_counts = _height_distribution()

    context = {
        'actresses':               page_obj,
        'page_obj':                page_obj,
        'paginator':               paginator,
        'filter_name':             name,
        'filter_country':          country,
        'filter_decade':           decade,
        'filter_height_min':       height_min,
        'filter_height_max':       height_max,
        'filter_min_rating':       min_rating,
        'sort':                    sort,
        'decade_choices':          DECADE_CHOICES,
        'chart_nationality_labels': json.dumps([s['nationality'] for s in nationality_stats]),
        'chart_nationality_counts': json.dumps([s['count']       for s in nationality_stats]),
        'chart_decade_labels':     json.dumps(decade_labels),
        'chart_decade_counts':     json.dumps(decade_counts),
        'chart_height_labels':     json.dumps(height_labels),
        'chart_height_counts':     json.dumps(height_counts),
    }
    return render(request, 'catalog/actress_list.html', context)


# ── Detail view ───────────────────────────────────────────────────────────────

def actress_detail(request, id):
    actress = get_object_or_404(Actress, id=id)

    featured_photo = (
        actress.photos.filter(is_featured=True).first()
        or actress.photos.first()
    )
    scenes = actress.favorite_scenes.all()

    return render(request, 'catalog/actress_detail.html', {
        'actress':        actress,
        'featured_photo': featured_photo,
        'scenes':         scenes,
    })


def _get_image_dimensions(image_file):
    """Return (width, height) tuple from an image file, or (None, None) on failure."""
    try:
        from PIL import Image as PILImage
        image_file.seek(0)
        img = PILImage.open(image_file)
        img.verify()
        image_file.seek(0)
        img = PILImage.open(image_file)
        return img.width, img.height
    except Exception:
        return None, None


# ── Photo: upload ─────────────────────────────────────────────────────────────

@require_POST
def upload_photos(request, id):
    actress = get_object_or_404(Actress, id=id)
    files   = request.FILES.getlist('photos')

    for f in files:
        w, h  = _get_image_dimensions(f)
        photo = Photo(actress=actress, width=w, height=h)
        photo.image.save(f.name, f, save=True)

    return redirect('actress_detail', id=id)


# ── Photo: delete ─────────────────────────────────────────────────────────────

@require_POST
def delete_photo(request, photo_id):
    photo      = get_object_or_404(Photo, id=photo_id)
    actress_id = photo.actress.id

    photo.image.delete(save=False)
    photo.delete()

    return redirect('actress_detail', id=actress_id)


# ── Photo: set as featured ────────────────────────────────────────────────────

@require_POST
def set_featured_photo(request, photo_id):
    photo   = get_object_or_404(Photo, id=photo_id)
    actress = photo.actress

    actress.photos.update(is_featured=False)
    photo.is_featured = True
    photo.save()

    return redirect('actress_detail', id=actress.id)
