from django.contrib import admin
from .models import Actress, Movie, FavoriteScene, Photo, StagedActress, StagedPhoto, ScrapingTask, Tag


class PhotoInline(admin.TabularInline):
    model           = Photo
    extra           = 1
    fields          = ['thumbnail', 'image', 'caption', 'is_featured', 'is_hd']
    readonly_fields = ['thumbnail']

    def thumbnail(self, obj):
        from django.utils.html import format_html
        if obj.image:
            return format_html(
                '<img src="{}" style="height:60px;border-radius:4px;object-fit:cover;">',
                obj.image.url
            )
        return '—'
    thumbnail.short_description = 'Preview'


@admin.register(Actress)
class ActressAdmin(admin.ModelAdmin):
    inlines       = [PhotoInline]
    list_display  = ['name', 'nationality', 'birth_country', 'date_of_birth', 'rating', 'photo_count']
    search_fields = ['name', 'birth_country', 'nationality']
    list_filter   = ['nationality', 'birth_country', 'rating']
    fieldsets = (
        (None, {'fields': ('name', 'rating')}),
        ('Biography', {'fields': ('date_of_birth', 'birth_country', 'nationality', 'height_cm', 'weight_kg', 'years_active_start', 'years_active_end')}),
        ('Online', {'fields': ('official_website', 'onlyfans_url', 'twitter_url', 'instagram_url')}),
        ('Tags', {'fields': ('tags',)}),
        ('Notes', {'fields': ('notes',)}),
    )

    def photo_count(self, obj):
        return obj.photos.count()
    photo_count.short_description = 'Photos'


@admin.register(FavoriteScene)
class FavoriteSceneAdmin(admin.ModelAdmin):
    list_display  = ['actress', 'title', 'rating', 'added_at']
    search_fields = ['actress__name', 'title', 'description']
    list_filter   = ['rating', 'actress']


@admin.register(StagedActress)
class StagedActressAdmin(admin.ModelAdmin):
    list_display    = ['query', 'name', 'status', 'birth_country', 'scraped_at']
    list_filter     = ['status']
    search_fields   = ['query', 'name']
    readonly_fields = ['query', 'scraped_at', 'error']


@admin.register(StagedPhoto)
class StagedPhotoAdmin(admin.ModelAdmin):
    list_display    = ['actress', 'gallery_title', 'status', 'is_duplicate', 'scraped_at', 'preview']
    list_filter     = ['status', 'is_duplicate', 'actress']
    search_fields   = ['actress__name', 'gallery_title']
    readonly_fields = ['preview', 'scraped_at', 'source_url_460', 'source_url_1280', 'image_hash']

    def preview(self, obj):
        from django.utils.html import format_html
        if obj.local_file:
            return format_html(
                '<img src="{}" style="height:60px;border-radius:4px;object-fit:cover;">',
                obj.local_file.url
            )
        return '—'
    preview.short_description = 'Preview'


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display  = ['title', 'release_year']
    search_fields = ['title']


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display    = ['actress', 'caption', 'is_featured', 'is_hd', 'dimensions']
    list_filter     = ['is_featured', 'is_hd', 'actress']
    readonly_fields = ['image_hash', 'width', 'height']

    def dimensions(self, obj):
        if obj.width and obj.height:
            return f"{obj.width}×{obj.height}"
        return '—'
    dimensions.short_description = 'Size'


@admin.register(ScrapingTask)
class ScrapingTaskAdmin(admin.ModelAdmin):
    list_display = ['task_type', 'status', 'actress', 'label', 'progress', 'total', 'pct', 'created_at']
    list_filter = ['status', 'task_type']
    readonly_fields = ['pct', 'created_at', 'updated_at']
    fieldsets = (
        (None, {'fields': ('task_type', 'status', 'actress', 'label')}),
        ('Progress', {'fields': ('progress', 'total', 'pct', 'message')}),
        ('Result', {'fields': ('error',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at', 'finished_at')}),
    )


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'category']
    list_filter = ['category']
    search_fields = ['name']
