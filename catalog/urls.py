from django.urls import path
from . import views

# A note on URL structure:
#   /actresses/          → list of all actresses
#   /actresses/3/        → detail page for actress #3
#   /actresses/3/upload/ → POST: upload photos for actress #3
#   /photos/7/delete/    → POST: delete photo #7
#   /photos/7/featured/  → POST: set photo #7 as the featured/profile photo

urlpatterns = [
    # ── Actress pages ──────────────────────────────────────────────────────
    path('actresses/',              views.actress_list,   name='actress_list'),
    path('actresses/<int:id>/',     views.actress_detail, name='actress_detail'),

    # ── Photo actions ──────────────────────────────────────────────────────
    # upload: lives under the actress URL because we need the actress id
    path('actresses/<int:id>/upload/', views.upload_photos, name='upload_photos'),

    # delete & set-featured: live under /photos/ because we only need the photo id
    path('photos/<int:photo_id>/delete/',   views.delete_photo,       name='delete_photo'),
    path('photos/<int:photo_id>/featured/', views.set_featured_photo, name='set_featured_photo'),
]
