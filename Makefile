.PHONY: dev emulators seed test lint deploy-dev

emulators:
	firebase emulators:start --project=scout-test

dev:
	uvicorn app.main:app --reload --port 8000 --env-file .env

seed:
	python -m scripts.seed_fake_data

test:
	firebase emulators:exec --project=scout-test \
	  --only=firestore,auth,storage \
	  "pytest --cov=app --cov-report=term-missing"

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
