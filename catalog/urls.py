from django.urls import path
from . import views

urlpatterns = [
    # Actress list + detail
    path('actresses/', views.actress_list, name='actress_list'),
    path('actresses/compare/', views.compare_actresses, name='compare_actresses'),
    path('actresses/<int:id>/', views.actress_detail, name='actress_detail'),

    # Manual photo upload / management
    path('actresses/<int:id>/upload-photos/',      views.upload_photos,      name='upload_photos'),
    path('photos/<int:photo_id>/delete/',          views.delete_photo,        name='delete_photo'),
    path('photos/<int:photo_id>/set-featured/',    views.set_featured_photo,  name='set_featured_photo'),
    path('photos/<int:photo_id>/upgrade/',         views.upgrade_photo,       name='upgrade_photo'),

    # Bulk IAFD import + staged review
    path('import/',                                views.bulk_import,         name='bulk_import'),
    path('import/review/',                         views.staged_review,       name='staged_review'),
    path('import/process-one/',                    views.import_process_one,  name='import_process_one'),
    path('import/approve/<int:staged_id>/',        views.approve_staged,      name='approve_staged'),
    path('import/reject/<int:staged_id>/',         views.reject_staged,       name='reject_staged'),
    path('import/repick/<int:staged_id>/',         views.repick_iafd_result,  name='repick_iafd_result'),
    path('import/clear-errors/',                   views.clear_staged_errors, name='clear_staged_errors'),

    # Actress info update + IAFD refresh
    path('actresses/<int:actress_id>/update/',          views.update_actress_info,   name='update_actress_info'),
    path('actresses/<int:actress_id>/refresh-iafd/',    views.refresh_actress_iafd,  name='refresh_actress_iafd'),
    path('actresses/<int:actress_id>/rate/',            views.set_actress_rating,    name='set_actress_rating'),
    path('bulk-refresh-iafd/',                          views.bulk_refresh_all_iafd, name='bulk_refresh_all_iafd'),

    # Photo scraping — two-stage AJAX progress
    path('actresses/<int:actress_id>/scrape-photos/',      views.scrape_photos_for_actress, name='scrape_photos_for_actress'),
    path('actresses/<int:actress_id>/scrape-start/',       views.scrape_photos_start,       name='scrape_photos_start'),
    path('actresses/<int:actress_id>/scrape-gallery/',     views.scrape_gallery_batch,      name='scrape_gallery_batch'),
    path('actresses/<int:actress_id>/photo-review/',       views.photo_review,              name='photo_review'),
    path('actresses/<int:actress_id>/reject-gallery/',     views.reject_gallery_photos,     name='reject_gallery_photos'),
    path('actresses/<int:actress_id>/scrape-full-album/',  views.scrape_full_album,         name='scrape_full_album'),

    # Scenes
    path('actresses/<int:actress_id>/scenes/add/',         views.add_scene,                 name='add_scene'),
    path('scenes/<int:scene_id>/delete/',                  views.delete_scene,              name='delete_scene'),

    # Bulk AJAX: staged photos
    path('staged-photos/bulk-approve/',                    views.bulk_approve_staged_photos, name='bulk_approve_staged_photos'),
    path('staged-photos/bulk-reject/',                     views.bulk_reject_staged_photos,  name='bulk_reject_staged_photos'),
    path('staged-photos/<int:staged_photo_id>/approve/',   views.approve_photo,              name='approve_photo'),
    path('staged-photos/<int:staged_photo_id>/reject/',    views.reject_photo,               name='reject_photo'),

    # Bulk AJAX: photos
    path('photos/bulk-delete/',   views.bulk_delete_photos,  name='bulk_delete_photos'),
    path('photos/bulk-upgrade/',  views.bulk_upgrade_photos, name='bulk_upgrade_photos'),

    # Single-name scraper utility
    path('test-scraper/', views.test_scraper, name='test_scraper'),

    # Export / backup
    path('export/', views.export_backup, name='export_backup'),

    # Background tasks — polling
    path('tasks/<int:task_id>/status/', views.task_status,  name='task_status'),
    path('tasks/active/',               views.tasks_active, name='tasks_active'),

    # IAFD rescrape UI
    path('rescrape/',                   views.rescrape_ui,      name='rescrape_ui'),
    path('rescrape/start/',             views.rescrape_start,   name='rescrape_start'),

    # Background photo scrape (replaces synchronous scrape_photos_for_actress)
    path('actresses/<int:actress_id>/scrape-photos-bg/', views.scrape_photos_bg, name='scrape_photos_bg'),
]
