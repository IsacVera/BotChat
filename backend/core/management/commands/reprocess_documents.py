from django.core.management.base import BaseCommand
from core.models import Document
from core.tasks import ingest_document


class Command(BaseCommand):
    help = 'Reprocess documents to regenerate chunks (useful after chunking algorithm updates)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--document-id',
            type=int,
            help='Reprocess specific document by ID',
        )
        parser.add_argument(
            '--company-id',
            type=int,
            help='Reprocess all documents for a specific company',
        )

    def handle(self, *args, **options):
        doc_id = options.get('document_id')
        company_id = options.get('company_id')

        if doc_id:
            docs = Document.objects.filter(id=doc_id)
            if not docs.exists():
                self.stdout.write(self.style.ERROR(f'Document {doc_id} not found'))
                return
        elif company_id:
            docs = Document.objects.filter(company_id=company_id)
        else:
            docs = Document.objects.all()

        total = docs.count()
        self.stdout.write(f'Reprocessing {total} document(s)...\n')

        for doc in docs:
            self.stdout.write(f'Processing: {doc.filename} (ID={doc.id})')
            
            # Delete existing chunks
            deleted_count = doc.chunks.count()
            doc.chunks.all().delete()
            self.stdout.write(f'  Deleted {deleted_count} old chunks')
            
            # Reset document status
            doc.status = 'uploaded'
            doc.error_message = ''
            doc.page_count = 0
            doc.save()
            
            # Trigger reprocessing
            try:
                # Try async
                ingest_document.delay(doc.id)
                self.stdout.write(self.style.SUCCESS(f'  Queued for reprocessing'))
            except Exception:
                # Fallback to sync
                try:
                    ingest_document(doc.id)
                    self.stdout.write(self.style.SUCCESS(f'  Reprocessed synchronously'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  Failed: {e}'))

        self.stdout.write(self.style.SUCCESS(f'\nReprocessing initiated for {total} document(s)'))
