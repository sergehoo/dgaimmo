from config.celery import app
from ai_engine.services import analyze_property_document
from mutuelles.models import Mutuelle
from real_estate.models import PropertyDocument, RealEstateProgram
from real_estate.services import compute_mutuelle_score, compute_program_score


@app.task
def refresh_mutuelle_real_estate_scores(mutuelle_id):
    mutuelle = Mutuelle.objects.get(id=mutuelle_id)
    compute_mutuelle_score(mutuelle)
    for program in RealEstateProgram.objects.filter(mutuelle=mutuelle):
        compute_program_score(mutuelle, program)


@app.task
def process_property_document_ocr(document_id):
    document = PropertyDocument.all_objects.select_related("mutuelle", "program").get(id=document_id)
    payload = analyze_property_document(document)
    document.ocr_payload = payload
    document.verified = payload["decision"] == "verified"
    document.save(update_fields=["ocr_payload", "verified", "updated_at"])
    return payload
