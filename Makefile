.PHONY: dev emulators seed test lint deploy-dev

emulators:
	firebase emulators:start --project=scout-test

dev:
	uvicorn app.main:app --reload --port 8000 --env-file .env

seed:
	.venv/bin/python -m scripts.seed_fake_data

seed_real:
	.venv/bin/python -m scripts.seed_real_data --project scout-497021 --spots 8

test:
	firebase emulators:exec --project=scout-test \
	  --only=firestore,auth,storage \
	  ".venv/bin/pytest --cov=app --cov-report=term-missing"

lint:
	ruff check app tests
	ruff format --check app tests

deploy-dev:
	gcloud run deploy scout-backend-dev \
	  --source . \
	  --region us-central1 \
	  --min-instances 0 \
	  --cpu-boost \
	  --allow-unauthenticated
