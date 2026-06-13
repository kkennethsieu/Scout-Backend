.PHONY: dev dev-device emulators seed test lint deploy-dev deploy-hosting

emulators:
	firebase emulators:start --project=scout-test

dev:
	uvicorn app.main:app --reload --port 8000 --env-file .env

# Run against the REAL scout-497021 project, bound to 0.0.0.0 so a physical
# device (via ngrok or LAN) can reach it. Uses .env.device. Pair with `ngrok http 8000`.
dev-device:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --env-file .env.device

seed:
	.venv/bin/python -m scripts.seed_fake_data

seed_real:
	.venv/bin/python -m scripts.seed_real_data --project scout-497021 --yes

test:
	firebase emulators:exec --project=scout-test \
	  --only=firestore,auth,storage \
	  ".venv/bin/pytest --cov=app --cov-report=term-missing"

lint:
	ruff check app tests
	ruff format --check app tests

# Deploy the static legal pages (privacy / terms) to Firebase Hosting.
deploy-hosting:
	firebase deploy --only hosting --project scout-497021

deploy-dev:
	gcloud run deploy scout-backend-dev \
	  --source . \
	  --region us-central1 \
	  --min-instances 0 \
	  --cpu-boost \
	  --allow-unauthenticated
