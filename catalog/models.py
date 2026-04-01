from django.db import models

# Create your models here.


class Actress(models.Model):
    name = models.CharField(max_length=200)
    date_of_birth = models.DateField(null=True, blank=True)
    years_active_start = models.PositiveSmallIntegerField(null=True, blank=True)
    years_active_end = models.PositiveSmallIntegerField(null=True, blank=True)
    height_cm = models.PositiveSmallIntegerField(null=True, blank=True)
    weight_kg = models.PositiveSmallIntegerField(null=True, blank=True)
    birth_country = models.CharField(max_length=100)
    official_website = models.URLField(blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Movie(models.Model):
    title = models.CharField(max_length=255)
    release_year = models.PositiveSmallIntegerField(null=True, blank=True)
    actresses = models.ManyToManyField(Actress, related_name="movies", blank=True)

    def __str__(self):
        return self.title


class FavoriteScene(models.Model):
    actress = models.ForeignKey(Actress, on_delete=models.CASCADE, related_name="favorite_scenes")
    movie = models.ForeignKey(Movie, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField()
    scene_link = models.URLField(blank=True)

    def __str__(self):
        return f"{self.actress.name} - {self.description[:40]}"


class Photo(models.Model):
    actress = models.ForeignKey(Actress, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="actresses/")
    caption = models.CharField(max_length=200, blank=True)
    is_featured = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.actress.name} photo"