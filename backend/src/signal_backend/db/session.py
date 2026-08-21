from sqlmodel import Session, create_engine

from signal_backend.config import settings

engine = create_engine(settings.database_url)


def get_session():
    # expire_on_commit=False: a commit mid-request (e.g. looping over several
    # candidates in the shortlist endpoint) would otherwise expire objects
    # returned earlier in the same request, breaking response serialization.
    with Session(engine, expire_on_commit=False) as session:
        yield session
