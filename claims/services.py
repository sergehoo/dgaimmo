from django.utils import timezone

from claims.models import AssistanceClaim


def advance_claim(claim):
    transitions = {
        AssistanceClaim.Status.DRAFT: AssistanceClaim.Status.SUBMITTED,
        AssistanceClaim.Status.SUBMITTED: AssistanceClaim.Status.REVIEW,
        AssistanceClaim.Status.REVIEW: AssistanceClaim.Status.APPROVED,
        AssistanceClaim.Status.APPROVED: AssistanceClaim.Status.PAID,
        AssistanceClaim.Status.PAID: AssistanceClaim.Status.CLOSED,
    }
    if claim.status not in transitions:
        return claim
    claim.status = transitions[claim.status]
    if claim.status == AssistanceClaim.Status.APPROVED and not claim.approved_amount:
        claim.approved_amount = claim.amount
    if claim.status == AssistanceClaim.Status.PAID:
        claim.paid_at = timezone.now()
    claim.save(update_fields=["status", "approved_amount", "paid_at", "updated_at"])
    return claim
