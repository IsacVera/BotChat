import os
import shutil
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404
from django.db import connection
from django.utils import timezone

from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework import status

from core.models import Document, Company, Chunk, ChatSession, ChatTurn, User
from .serializer import DocumentSerializer, AskSerializer, CompanySerializer, UserSignupSerializer, UserLoginSerializer
from .gemini import classify_question, answer_question, embed_texts

# Ingestion task
try:
    from core.tasks import ingest_document
except Exception:  # pragma: no cover
    ingest_document = None


# Helper: check if a company has any indexed chunks on ready docs

def _has_indexed_content(company_id: int) -> bool:
    return Chunk.objects.filter(company_id=company_id, document__status='ready').exists()


def _company_name(company_id: int) -> str:
    company = Company.objects.filter(id=company_id).first()
    return company.name if company else f"Company {company_id}"


def _reset_company_documents(company_id: int) -> None:
    docs_dir = os.path.join(settings.MEDIA_ROOT, 'docs', str(company_id))
    if os.path.isdir(docs_dir):
        shutil.rmtree(docs_dir)
    Document.objects.filter(company_id=company_id).delete()


def _fixed_pdf_source_dir() -> str:
    return os.getenv('DEFAULT_PDF_DIR', os.path.join(settings.MEDIA_ROOT, 'source'))


def _get_fixed_pdf_source() -> str:
    source_dir = _fixed_pdf_source_dir()
    if not os.path.isdir(source_dir):
        raise FileNotFoundError(f'Configured PDF folder does not exist: {source_dir}')

    pdf_files = sorted(
        name for name in os.listdir(source_dir)
        if os.path.isfile(os.path.join(source_dir, name)) and name.lower().endswith('.pdf')
    )
    if not pdf_files:
        raise FileNotFoundError(f'No PDF found in configured folder: {source_dir}')
    if len(pdf_files) > 1:
        raise FileExistsError(f'Expected exactly one PDF in {source_dir}, found {len(pdf_files)}')
    return os.path.join(source_dir, pdf_files[0])


def _ensure_company(company_id: int) -> Company:
    company = Company.objects.filter(id=company_id).first()
    if company:
        return company
    company = Company(id=company_id, name=f"Company {company_id}")
    company.save()
    return company


def _enqueue_ingestion(doc: Document) -> None:
    if not ingest_document:
        return
    try:
        ingest_document.delay(doc.id)
    except Exception:
        try:
            ingest_document.run(doc.id)
        except Exception:
            pass


def _create_document_from_source(company_id: int, source_path: str) -> Document:
    company = _ensure_company(company_id)
    _reset_company_documents(company_id)

    dir_path = os.path.join(settings.MEDIA_ROOT, 'docs', str(company_id))
    os.makedirs(dir_path, exist_ok=True)
    _, ext = os.path.splitext(source_path)
    storage_path = os.path.join('docs', str(company_id), f'source{ext.lower() or ".pdf"}')
    destination_path = os.path.join(settings.MEDIA_ROOT, storage_path)
    shutil.copyfile(source_path, destination_path)

    doc = Document.objects.create(
        company=company,
        filename=os.path.basename(source_path),
        storage_path=storage_path,
        status='uploaded',
    )
    _enqueue_ingestion(doc)
    return doc


def _public_topk(rows):
    return [
        {
            'chunk_id': r['id'],
            'score': r['score'],
            'page_from': r['page_from'],
            'page_to': r['page_to'],
        }
        for r in rows
    ]


def _topk_chunks(company_id: int, question: str, k: int = 6):
    """
    Retrieve top-k most relevant chunks using hybrid search (vector + keyword).
    Falls back to keyword-only if embeddings unavailable.
    """
    # Try vector+keyword hybrid; fallback to keyword-only if vectors missing
    # Compute question embedding
    try:
        q_vec = embed_texts([question])[0]
        q_literal = '[' + ','.join(f"{x:.6f}" for x in q_vec) + ']'
        with connection.cursor() as cur:
            cur.execute(
                """
                WITH vec_candidates AS (
                  SELECT id, text, page_from, page_to,
                         1 - (embedding_vec <=> %s::vector) AS vscore
                  FROM core_chunk
                  WHERE company_id = %s AND embedding_vec IS NOT NULL
                  ORDER BY embedding_vec <-> %s::vector
                  LIMIT 20
                ),
                kw AS (
                  SELECT id, similarity(text, %s) AS kscore
                  FROM core_chunk
                  WHERE company_id = %s
                  ORDER BY text <-> %s
                  LIMIT 50
                )
                SELECT c.id, c.text, c.page_from, c.page_to,
                       (coalesce(v.vscore,0)*0.7 + coalesce(k.kscore,0)*0.3) AS score
                FROM core_chunk c
                LEFT JOIN vec_candidates v ON v.id=c.id
                LEFT JOIN kw k ON k.id=c.id
                WHERE c.company_id = %s
                ORDER BY score DESC
                LIMIT %s
                """,
                [q_literal, company_id, q_literal, question, company_id, question, company_id, k]
            )
            rows = cur.fetchall()
        return [
            { 'id': r[0], 'text': r[1], 'page_from': r[2], 'page_to': r[3], 'score': float(r[4]) }
            for r in rows
        ]
    except Exception as e:
        # keyword-only fallback
        # Log the error for debugging
        print(f"Vector search failed, falling back to keyword-only: {e}")
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT id, text, page_from, page_to, similarity(text, %s) AS score
                FROM core_chunk
                WHERE company_id = %s
                ORDER BY text <-> %s
                LIMIT %s
                """,
                [question, company_id, question, k]
            )
            rows = cur.fetchall()
        return [
            { 'id': r[0], 'text': r[1], 'page_from': r[2], 'page_to': r[3], 'score': float(r[4]) }
            for r in rows
        ]


@api_view(['POST'])
def docs_upload(request):
    file = request.FILES.get('file')
    company_id = request.POST.get('company_id') or os.getenv('DEFAULT_COMPANY_ID', '1')
    if not file or not company_id:
        return Response({'error': 'file and company_id are required'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        company_id = int(company_id)
    except ValueError:
        return Response({'error': 'company_id must be an integer'}, status=status.HTTP_400_BAD_REQUEST)

    company = _ensure_company(company_id)

    # Single-document mode: replace any previous upload for this company.
    _reset_company_documents(company_id)

    # Save file to MEDIA_ROOT/docs/<company_id>/
    dir_path = os.path.join(settings.MEDIA_ROOT, 'docs', str(company_id))
    os.makedirs(dir_path, exist_ok=True)
    _, ext = os.path.splitext(file.name)
    storage_path = os.path.join('docs', str(company_id), f'source{ext.lower() or ".pdf"}')
    # write file relative to MEDIA_ROOT
    default_storage.save(storage_path, ContentFile(file.read()))

    doc = Document.objects.create(
        company=company,
        filename=file.name,
        storage_path=storage_path,
        status='uploaded',
    )

    _enqueue_ingestion(doc)

    return Response({'document_id': doc.id, 'status': doc.status}, status=200)


@api_view(['POST'])
def docs_load_default(request):
    company_id_raw = request.data.get('company_id') or os.getenv('DEFAULT_COMPANY_ID', '1')
    try:
        company_id = int(company_id_raw)
    except (TypeError, ValueError):
        return Response({'error': 'company_id must be an integer'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        source_path = _get_fixed_pdf_source()
        doc = _create_document_from_source(company_id, source_path)
    except (FileNotFoundError, FileExistsError) as exc:
        return Response({
            'error': str(exc),
            'source_dir': _fixed_pdf_source_dir(),
        }, status=status.HTTP_400_BAD_REQUEST)

    return Response({
        'document_id': doc.id,
        'status': doc.status,
        'filename': doc.filename,
        'source_dir': _fixed_pdf_source_dir(),
    }, status=200)


@api_view(['GET'])
def docs_list(request):
    company_id = request.query_params.get('company_id')
    if not company_id:
        return Response({'error': 'company_id is required as a query parameter'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        company_id = int(company_id)
    except ValueError:
        return Response({'error': 'company_id must be an integer'}, status=status.HTTP_400_BAD_REQUEST)

    docs = Document.objects.filter(company_id=company_id).order_by('-created_at')
    return Response(DocumentSerializer(docs, many=True).data, status=200)


@api_view(['GET'])
def docs_detail(request, doc_id: int):
    doc = get_object_or_404(Document, pk=doc_id)
    return Response(DocumentSerializer(doc).data, status=200)


@api_view(['POST'])
def chat_ask(request):
    s = AskSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    company_id = s.validated_data['company_id']
    question = s.validated_data['question']
    user_id = s.validated_data.get('user_id') or ''
    session_id = s.validated_data.get('session_id') or ''

    # Simple per-company daily quota
    max_per_day = int(os.getenv('COMPANY_DAILY_QUOTA', '0') or '0')
    if max_per_day > 0:
        today = timezone.now().date()
        used = ChatTurn.objects.filter(session__company_id=company_id, created_at__date=today).count()
        if used >= max_per_day:
            return Response({'error': 'Daily quota reached for this company.'}, status=status.HTTP_429_TOO_MANY_REQUESTS)

    if not _has_indexed_content(company_id):
        return Response({'error': 'Please upload a PDF before asking the chatbot any questions.'}, status=status.HTTP_400_BAD_REQUEST)

    company_name = _company_name(company_id)

    # Retrieval
    topk = _topk_chunks(company_id, question)
    # Use full chunk text (already sized appropriately during chunking ~800 words)
    snippets = [c['text'] for c in topk]

    # Classifier
    try:
        classifier = classify_question(company_name=company_name, user_question=question, context_snippets=snippets)
    except Exception:
        return Response({'error': 'Upstream AI service error. Please try again later.'}, status=status.HTTP_502_BAD_GATEWAY)

    # Persist session/turn (create session lazily)
    if session_id:
        session = ChatSession.objects.filter(id=session_id, company_id=company_id).first()
    else:
        session = None
    if not session:
        session = ChatSession.objects.create(company_id=company_id, user_id=user_id or '')

    turn = ChatTurn.objects.create(
        session=session,
        user_question=question,
        sanitized_query=classifier.get('sanitized_query', question),
        related=classifier.get('related'),
        policy_tags=classifier.get('policy_tags', []),
        reason=classifier.get('reason', ''),
        topk_chunks=[{'id': c['id'], 'score': c['score'], 'page_from': c['page_from'], 'page_to': c['page_to']} for c in topk],
    )

    if not classifier.get('related', True):
        return Response({
            'classifier': classifier,
            'answer': None,
            'debug': {'topk': _public_topk(topk)}
        }, status=200)

    # Answerer
    try:
        answer = answer_question(
            company_name=company_name,
            sanitized_query=classifier.get('sanitized_query') or question,
            policy_tags=classifier.get('policy_tags', []),
            context_snippets=snippets
        )
    except Exception:
        return Response({'error': 'Upstream AI service error. Please try again later.'}, status=status.HTTP_502_BAD_GATEWAY)

    # Save answer
    turn.answer_json = answer
    turn.save(update_fields=['answer_json'])

    return Response({
        'classifier': classifier,
        'answer': answer,
        'debug': {'topk': _public_topk(topk)}
    }, status=200)


@api_view(['POST'])
def chat_policy_check(request):
    """Lightweight endpoint to verify AI key and policy classification without requiring indexed content."""
    s = AskSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    company_id = s.validated_data['company_id']
    question = s.validated_data['question']
    company_name = _company_name(company_id)
    try:
        classifier = classify_question(company_name=company_name, user_question=question)
        return Response({'classifier': classifier}, status=200)
    except Exception:
        return Response({'error': 'Upstream AI service error. Please verify GEMINI_API_KEY and network.'}, status=status.HTTP_502_BAD_GATEWAY)


@api_view(['POST'])
def company_create(request):
    """Create a new company"""
    serializer = CompanySerializer(data=request.data)
    if serializer.is_valid():
        company = serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def user_signup(request):
    """Create a new user account and company in one atomic operation"""
    serializer = UserSignupSerializer(data=request.data)
    if serializer.is_valid():
        # Create the company first
        company = Company.objects.create(
            name=serializer.validated_data['company_name']
        )
        
        # Create the user
        user = User.objects.create_user(
            username=serializer.validated_data['username'],
            email=serializer.validated_data['email'],
            password=serializer.validated_data['password']
        )
        
        # Link user to the newly created company
        user.companies.add(company)
        
        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'company_id': company.id,
            'company_name': company.name
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def user_login(request):
    """Authenticate user with username/email and password"""
    serializer = UserLoginSerializer(data=request.data)
    if serializer.is_valid():
        identifier = serializer.validated_data['identifier']
        password = serializer.validated_data['password']
        
        # Try to find user by username or email
        user = None
        if '@' in identifier:
            # Looks like an email
            user = User.objects.filter(email=identifier).first()
        else:
            # Assume username
            user = User.objects.filter(username=identifier).first()
        
        # Check if user exists and password is correct
        if user and user.check_password(password):
            # Get user's companies
            company_ids = list(user.companies.values_list('id', flat=True))
            
            return Response({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'company_ids': company_ids
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': 'Invalid credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
