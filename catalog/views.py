from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST   # only allow POST requests
from django.db.models import Count
from .models import Actress, Photo
import json


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
    actresses = Actress.objects.all()

    # Read filter values from the URL (?name=…&country=…&decade=…&height_min=…)
    country    = request.GET.get('country', '').strip()
    decade     = request.GET.get('decade', '')
    height_min = request.GET.get('height_min', '')
    height_max = request.GET.get('height_max', '')
    name       = request.GET.get('name', '').strip()

    # Apply filters — each one only runs if the user actually typed something
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

    # Chart data — always built from the full dataset, not the filtered one
    country_stats  = (
        Actress.objects.values('birth_country')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    decade_labels, decade_counts = _decade_distribution()
    height_labels, height_counts = _height_distribution()

    context = {
        'actresses': actresses,

        # echo filter values back so the form keeps its state
        'filter_name':       name,
        'filter_country':    country,
        'filter_decade':     decade,
        'filter_height_min': height_min,
        'filter_height_max': height_max,
        'decade_choices':    DECADE_CHOICES,

        # chart data
        'chart_country_labels': json.dumps([s['birth_country'] for s in country_stats]),
        'chart_country_counts': json.dumps([s['count']         for s in country_stats]),
        'chart_decade_labels':  json.dumps(decade_labels),
        'chart_decade_counts':  json.dumps(decade_counts),
        'chart_height_labels':  json.dumps(height_labels),
        'chart_height_counts':  json.dumps(height_counts),
    }
    return render(request, 'catalog/actress_list.html', context)


# ── Detail view ───────────────────────────────────────────────────────────────

def actress_detail(request, id):
    actress = get_object_or_404(Actress, id=id)

    # Try to find the photo explicitly marked as featured.
    # If none is marked, fall back to the first photo uploaded.
    # If there are no photos at all, this will be None (the template handles that).
    featured_photo = (
        actress.photos.filter(is_featured=True).first()
        or actress.photos.first()
    )

    return render(request, 'catalog/actress_detail.html', {
        'actress':       actress,
        'featured_photo': featured_photo,
    })


# ── Photo: upload ─────────────────────────────────────────────────────────────
# request.FILES.getlist('photos') returns a list of all files the user selected.
# We loop through and create one Photo record per file.

@require_POST   # this view only accepts form submissions, never a plain page load
def upload_photos(request, id):
    actress = get_object_or_404(Actress, id=id)
    files   = request.FILES.getlist('photos')   # 'photos' must match the input name=""

    for f in files:
        Photo.objects.create(actress=actress, image=f)

    # After uploading, send the user back to the detail page
    return redirect('actress_detail', id=id)


# ── Photo: delete ─────────────────────────────────────────────────────────────
# We delete the file from disk AND the database row.
# photo.image.delete(save=False) removes the actual file.
# photo.delete() removes the database row.

@require_POST
def delete_photo(request, photo_id):
    photo      = get_object_or_404(Photo, id=photo_id)
    actress_id = photo.actress.id          # save this before we delete the photo

    photo.image.delete(save=False)         # delete the file from disk
    photo.delete()                         # delete the database row

    return redirect('actress_detail', id=actress_id)


# ── Photo: set as featured ────────────────────────────────────────────────────
# Step 1: set is_featured = False on every photo belonging to this actress
# Step 2: set is_featured = True on just the chosen photo
# This guarantees exactly one (or zero) featured photos at any time.

@require_POST
def set_featured_photo(request, photo_id):
    photo   = get_object_or_404(Photo, id=photo_id)
    actress = photo.actress

    actress.photos.update(is_featured=False)   # clear all
    photo.is_featured = True
    photo.save()

    return redirect('actress_detail', id=actress.id)
