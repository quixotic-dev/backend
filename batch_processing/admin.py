from django.contrib import admin
from . import models


@admin.register(models.BatchJob)
class BatchJobAdmin(admin.ModelAdmin):
    pass

@admin.register(models.StaleOwnerRecord)
class StaleOwnerRecordAdmin(admin.ModelAdmin):
    pass
