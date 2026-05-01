from fastapi import HTTPException


def not_found(exc: KeyError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc).strip("'"))

