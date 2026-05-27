from django.contrib import admin

from ai_engine.models import AIAnalysis


@admin.register(AIAnalysis)
class AIAnalysisAdmin(admin.ModelAdmin):
    list_display = ("analysis_type", "provider", "confidence", "related_object_type", "created_at")
    list_filter = ("analysis_type", "provider")
    search_fields = ("prompt", "related_object_type", "related_object_id")
