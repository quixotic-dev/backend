from django.contrib import admin
from . import models

@admin.action(description='Refresh')
def refresh(modeladmin, request, queryset):
    for e in queryset:
        e.refresh()

@admin.register(models.HostedCollection)
class HostedCollectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'address', 'max_supply', 'featured']
    list_editable = ['featured']
    actions = [refresh]

@admin.register(models.HostedMetadata)
class HostedMetadataAdmin(admin.ModelAdmin):
    pass

@admin.register(models.GreenlistedAddress)
class HostedMetadataAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'collection']
    list_filter = [
        ['collection', admin.RelatedOnlyFieldListFilter],
    ]

