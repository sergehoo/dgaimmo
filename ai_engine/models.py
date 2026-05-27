from django.db import models

from core.models import TenantModel


class AIAnalysis(TenantModel):
    class Provider(models.TextChoices):
        OPENAI = "openai", "OpenAI compatible"
        OLLAMA = "ollama", "Ollama local"

    analysis_type = models.CharField(max_length=80, db_index=True)
    provider = models.CharField(max_length=24, choices=Provider.choices, default=Provider.OLLAMA, db_index=True)
    prompt = models.TextField()
    result = models.JSONField(default=dict, blank=True)
    confidence = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    related_object_type = models.CharField(max_length=120, blank=True)
    related_object_id = models.CharField(max_length=120, blank=True)

    class Meta:
        indexes = [models.Index(fields=["mutuelle", "analysis_type", "created_at"])]
