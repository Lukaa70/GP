from django.db import models
from django.utils import timezone


class Actress(models.Model):
    name               = models.CharField(max_length=200)
    date_of_birth      = models.DateField(null=True, blank=True)
    years_active_start = models.PositiveSmallIntegerField(null=True, blank=True)
    years_active_end   = models.PositiveSmallIntegerField(null=True, blank=True)
    height_cm          = models.PositiveSmallIntegerField(null=True, blank=True)
    weight_kg          = models.PositiveSmallIntegerField(null=True, blank=True)
    birth_country      = models.CharField(max_length=100)
    nationality        = models.CharField(max_length=100, blank=True)
    official_website   = models.URLField(blank=True)
    notes              = models.TextField(blank=True)

    # Rating 1-5 stars (null = unrated)
    rating = models.PositiveSmallIntegerField(null=True, blank=True)

    # Social links
    onlyfans_url  = models.URLField(blank=True)
    twitter_url   = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def featured_photo(self):
        return self.photos.filter(is_featured=True).first() or self.photos.first()

    @property
    def pending_staged_photos_count(self):
        return self.staged_photos.filter(status='pending').count()


class Movie(models.Model):
    title        = models.CharField(max_length=255)
    release_year = models.PositiveSmallIntegerField(null=True, blank=True)
    actresses    = models.ManyToManyField(Actress, related_name="movies", blank=True)

    def __str__(self):
        return self.title


class FavoriteScene(models.Model):
    actress     = models.ForeignKey(Actress, on_delete=models.CASCADE, related_name="favorite_scenes")
    movie       = models.ForeignKey(Movie, on_delete=models.SET_NULL, null=True, blank=True)
    title       = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)
    scene_link  = models.URLField(blank=True)
    rating      = models.PositiveSmallIntegerField(null=True, blank=True)  # 1-5
    added_at    = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.actress.name} — {self.title or self.description[:40]}"


class Photo(models.Model):
    actress         = models.ForeignKey(Actress, on_delete=models.CASCADE, related_name="photos")
    image           = models.ImageField(upload_to="actresses/")
    caption         = models.CharField(max_length=200, blank=True)
    is_featured     = models.BooleanField(default=False)
    source_url_1280 = models.URLField(max_length=500, blank=True)
    image_hash      = models.CharField(max_length=32, blank=True, db_index=True)
    is_hd           = models.BooleanField(default=False)
    width           = models.PositiveIntegerField(null=True, blank=True)
    height          = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.actress.name} photo"


# ── Staging: IAFD data ────────────────────────────────────────────────────────

class StagedActress(models.Model):

    class Status(models.TextChoices):
        PENDING  = 'pending',  'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        ERROR    = 'error',    'Error'

    query               = models.CharField(max_length=200)
    scraped_at          = models.DateTimeField(default=timezone.now)
    status              = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    iafd_url            = models.URLField(max_length=500, blank=True)
    iafd_search_results = models.JSONField(default=list, blank=True)

    name               = models.CharField(max_length=200, blank=True)
    date_of_birth      = models.DateField(null=True, blank=True)
    years_active_start = models.PositiveSmallIntegerField(null=True, blank=True)
    years_active_end   = models.PositiveSmallIntegerField(null=True, blank=True)
    height_cm          = models.PositiveSmallIntegerField(null=True, blank=True)
    weight_kg          = models.PositiveSmallIntegerField(null=True, blank=True)
    birth_country      = models.CharField(max_length=100, blank=True)
    error              = models.TextField(blank=True)

    class Meta:
        ordering = ['-scraped_at']

    def __str__(self):
        return f"{self.query} [{self.status}]"

    @property
    def has_alternatives(self):
        return len(self.iafd_search_results) > 1


# ── Staging: pornpics photos ──────────────────────────────────────────────────

class StagedPhoto(models.Model):

    class Status(models.TextChoices):
        PENDING  = 'pending',  'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    actress         = models.ForeignKey(Actress, on_delete=models.CASCADE, related_name="staged_photos")
    local_file      = models.ImageField(upload_to="staged_photos/", null=True, blank=True)
    source_url_460  = models.URLField(max_length=500)
    source_url_1280 = models.URLField(max_length=500, blank=True)
    gallery_title   = models.CharField(max_length=300, blank=True)
    gallery_url     = models.URLField(max_length=500, blank=True)
    status          = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    scraped_at      = models.DateTimeField(default=timezone.now)
    image_hash      = models.CharField(max_length=32, blank=True, db_index=True)
    is_duplicate    = models.BooleanField(default=False)

    class Meta:
        ordering = ['gallery_url', 'id']

    def __str__(self):
        return f"{self.actress.name} — staged photo [{self.status}]"


# ── Background task tracking ──────────────────────────────────────────────────

class ScrapingTask(models.Model):

    class TaskType(models.TextChoices):
        IAFD_SINGLE   = 'iafd_single',   'IAFD single actress'
        IAFD_BULK     = 'iafd_bulk',     'IAFD bulk rescrape'
        PHOTOS_SCRAPE = 'photos_scrape', 'Photo scraping'

    class Status(models.TextChoices):
        PENDING  = 'pending',  'Pending'
        RUNNING  = 'running',  'Running'
        DONE     = 'done',     'Done'
        ERROR    = 'error',    'Error'

    task_type  = models.CharField(max_length=20, choices=TaskType.choices)
    status     = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    actress    = models.ForeignKey(Actress, on_delete=models.SET_NULL, null=True, blank=True)
    label      = models.CharField(max_length=300, blank=True)  # human-readable description
    progress   = models.PositiveIntegerField(default=0)   # current step
    total      = models.PositiveIntegerField(default=0)   # total steps (0 = indeterminate)
    message    = models.TextField(blank=True)             # current status text
    error      = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.task_type} [{self.status}] {self.label}"

    @property
    def pct(self):
        if self.total and self.total > 0:
            return min(100, round(self.progress / self.total * 100))
        return 0 if self.status == 'running' else 100
