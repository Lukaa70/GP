from django.contrib import admin
from .models import Actress, Movie, FavoriteScene, Photo


# ── Photo inline ───────────────────────────────────────────────────────────
# This makes photos appear as a table *inside* the Actress edit page in admin.
# "extra = 3" means it shows 3 empty upload rows by default.

class PhotoInline(admin.TabularInline):
    model            = Photo
    extra            = 3                   # empty rows shown for new uploads
    fields           = ['thumbnail', 'image', 'caption', 'is_featured']
    readonly_fields  = ['thumbnail']

    def thumbnail(self, obj):
        from django.utils.html import format_html
        if obj.image:
            return format_html(
                '<img src="{}" style="height:60px;border-radius:4px;object-fit:cover;">',
                obj.image.url
            )
        return '—'
    thumbnail.short_description = 'Preview'


# ── Actress admin ──────────────────────────────────────────────────────────
@admin.register(Actress)
class ActressAdmin(admin.ModelAdmin):
    inlines       = [PhotoInline]
    list_display  = ['name', 'birth_country', 'date_of_birth', 'photo_count']
    search_fields = ['name', 'birth_country']
    list_filter   = ['birth_country']

    def photo_count(self, obj):
        return obj.photos.count()
    photo_count.short_description = 'Photos'


# ── Other models ───────────────────────────────────────────────────────────
@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display  = ['title', 'release_year']
    search_fields = ['title']


@admin.register(FavoriteScene)
class FavoriteSceneAdmin(admin.ModelAdmin):
    list_display  = ['actress', 'movie']
    search_fields = ['actress__name', 'movie__title']


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ['actress', 'caption', 'is_featured']
    list_filter  = ['actress']
