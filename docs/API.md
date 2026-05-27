# API MutuelleX

Base path: `/api/v1/`

Principes:

- Authentification JWT.
- Header tenant: `X-Mutuelle-ID`.
- Pagination standard `page`, `page_size`.
- Filtres DRF et recherche sur les ressources principales.
- Documentation OpenAPI: `/api/docs/`.

Endpoints importants:

- `POST /api/v1/auth/bootstrap-mutuelle/`
- `POST /api/v1/auth/token/`
- `POST /api/v1/payments/mobile-money/initiate/`
- `POST /api/v1/members/`
- `POST /api/v1/contribution-plans/`
- `POST /api/v1/real-estate/member-financial-profiles/`
- `POST /api/v1/real-estate/quotite-simulations/`
- `POST /api/v1/real-estate/opportunities/{id}/simulate-financing/`
- `POST /api/v1/real-estate/programs/{id}/score/`
- `POST /api/v1/real-estate/scores/member/`
- `POST /api/v1/real-estate/scores/mutuelle/`
- `GET /api/v1/real-estate/scores/dashboard/`
- `POST /api/v1/ai/analyses/real-estate-opportunity/`

## Parcours MVP

1. Créer la mutuelle et l'admin avec `auth/bootstrap-mutuelle`.
2. Envoyer `Authorization: Bearer <access>` et `X-Mutuelle-ID: <id>`.
3. Enrôler un membre avec `members`.
4. Ajouter son profil financier avec `real-estate/member-financial-profiles`.
5. Créer un programme, une opportunité et un lot immobilier.
6. Lancer `real-estate/quotite-simulations`.
7. Comparer un financement avec `opportunities/{id}/simulate-financing`.
8. Réserver un lot avec `real-estate/reservations`.
