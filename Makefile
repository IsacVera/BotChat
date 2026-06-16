# Variables
DC=docker compose
DOCK_PATH=docker/docker-compose.yml
FrontendStr=echo "Frontend http://localhost:4200"
BackendStr=echo "Backend http://localhost:8000"
START_UP_MESSAGE=&& $(FrontendStr) && $(BackendStr)
RUN=$(DC) -f $(DOCK_PATH)
exec-backend=exec backend python manage.py

# Docker commands
dev:
	$(RUN) up --build -d ${START_UP_MESSAGE}

debug:
	$(RUN) up --build ${START_UP_MESSAGE}

stop:
	$(RUN) down

restart:
	$(RUN) restart

reload-backend:
	$(RUN) up -d --force-recreate backend celery-worker

teardown:
	@make stop
	@docker volume rm $$(docker volume ls -q) || true
	@docker system prune -a --volumes --force

# Backend commands

create-migration:
	$(RUN) $(exec-backend) makemigrations

migrate:
	$(RUN) $(exec-backend) migrate

python-shell:
	$(RUN) $(exec-backend) shell

new-backend-app:
	@${RUN} $(exec-backend) startapp $(filter-out $@,$(MAKECMDGOALS))

create-and-migrate:
	@make create-migration
	@make migrate

wipe-data:
	@echo "Wiping all data except Users and Groups, plus uploaded PDFs..."
	$(RUN) exec backend python backend/manage.py shell -c "from core.models import Document, Chunk, Company, ChatSession, ChatTurn; ChatTurn.objects.all().delete(); ChatSession.objects.all().delete(); Chunk.objects.all().delete(); Document.objects.all().delete(); Company.objects.all().delete(); print('✓ All core data wiped (Users and Groups preserved)')"
	$(RUN) exec backend sh -c 'rm -rf /app/backend/media/docs/* && echo "✓ Uploaded PDFs cleared"'

# Frontend commands
logs-frontend:
	$(RUN) logs -f frontend

logs-backend:
	$(RUN) logs -f backend

logs-celery:
	$(RUN) logs -f celery-worker

logs-all:
	$(RUN) logs -f

print:
	$(RUN) exec backend python backend/manage.py shell -c "from core.models import Document, Chunk; doc = Document.objects.first(); print(f'Document: {doc.filename}'); print(f'Status: {doc.status}, Pages: {doc.page_count}'); print(); chunks = Chunk.objects.filter(document=doc).order_by('id'); [print(f'=== CHUNK {i} ===\nPages: {chunk.page_from}-{chunk.page_to}\nWord count: {len(chunk.text.split())}\n\nFull text:\n{chunk.text}\n\n' + '='*80 + '\n') for i, chunk in enumerate(chunks, 1)]"