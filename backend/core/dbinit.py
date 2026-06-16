from django.db import connection


def run_db_init():
    """
    Initialize Postgres extensions and vector/text indexes.
    Safe to run multiple times; uses IF NOT EXISTS.
    """
    with connection.cursor() as cur:
        # Enable required extensions
        try:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        except Exception:
            pass
        try:
            cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
        except Exception:
            pass

        # Add pgvector column for embeddings
        try:
            cur.execute(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='core_chunk' AND column_name='embedding_vec'
                    ) THEN
                        ALTER TABLE core_chunk ADD COLUMN embedding_vec vector(768);
                    END IF;
                END$$;
                """
            )
        except Exception:
            pass

        # Create indexes (ignore failures if extension not available yet)
        try:
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chunk_embedding
                ON core_chunk USING ivfflat (embedding_vec vector_l2_ops) WITH (lists = 100);
                """
            )
        except Exception:
            pass

        try:
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chunk_text_gin
                ON core_chunk USING gin (text gin_trgm_ops);
                """
            )
        except Exception:
            pass
