# utils/crud.py 
from sqlalchemy import (
    select, func, update as sql_update, delete as sql_delete,
    or_, and_, not_, cast, String, desc, asc
)
from sqlalchemy.orm import Session, selectinload
from typing import (
    Type, TypeVar, Generic, List, Optional, Dict, Any, 
    Union, Tuple, Callable
)
import re

ModelType = TypeVar("ModelType")


# ========== LOOKUP PARSER ==========

class LookupParser:
    """Django-style field lookups for SQLAlchemy in FastAPI."""
    
    LOOKUP_SEP = "__"
    
    @classmethod
    def parse(cls, model: Type, **lookups) -> List:
        """Parse multiple lookups into SQLAlchemy filter conditions."""
        conditions = []
        for field_lookup, value in lookups.items():
            conditions.append(cls._parse_single(model, field_lookup, value))
        return conditions
    
    @classmethod
    def _parse_single(cls, model: Type, field_lookup: str, value: Any) -> Any:
        """Parse single field__lookup=value into SQLAlchemy condition."""
        parts = field_lookup.split(cls.LOOKUP_SEP)
        
        # Handle related fields (merchant__wallet__iexact)
        if len(parts) > 2:
            current_model = model
            for part in parts[:-2]:
                relationship = getattr(current_model, part)
                current_model = relationship.property.mapper.class_
            field = getattr(current_model, parts[-2])
            lookup_type = parts[-1]
        elif len(parts) == 2:
            field = getattr(model, parts[0])
            lookup_type = parts[1]
        else:
            field = getattr(model, parts[0])
            lookup_type = "exact"
        
        method = getattr(cls, f"_lookup_{lookup_type}", cls._lookup_exact)
        return method(field, value)
    
    # Exactness
    @staticmethod
    def _lookup_exact(field, value): return field == value
    @staticmethod
    def _lookup_iexact(field, value): return func.lower(field) == func.lower(value)
    
    # Partial
    @staticmethod
    def _lookup_contains(field, value): return field.contains(value)
    @staticmethod
    def _lookup_icontains(field, value): return field.ilike(f"%{value}%")
    @staticmethod
    def _lookup_startswith(field, value): return field.startswith(value)
    @staticmethod
    def _lookup_istartswith(field, value): return field.ilike(f"{value}%")
    @staticmethod
    def _lookup_endswith(field, value): return field.endswith(value)
    @staticmethod
    def _lookup_iendswith(field, value): return field.ilike(f"%{value}")
    @staticmethod
    def _lookup_regex(field, value): return field.op("~")(value)
    @staticmethod
    def _lookup_iregex(field, value): return field.op("~*")(value)
    
    # Comparison
    @staticmethod
    def _lookup_gt(field, value): return field > value
    @staticmethod
    def _lookup_gte(field, value): return field >= value
    @staticmethod
    def _lookup_lt(field, value): return field < value
    @staticmethod
    def _lookup_lte(field, value): return field <= value
    @staticmethod
    def _lookup_range(field, value: Tuple[Any, Any]): return field.between(value[0], value[1])
    
    # Membership
    @staticmethod
    def _lookup_in(field, value: List[Any]): return field.in_(value)
    @staticmethod
    def _lookup_isnull(field, value: bool): 
        return field.is_(None) if value else field.isnot(None)
    
    # Dates
    @staticmethod
    def _lookup_year(field, value): return func.extract("year", field) == value
    @staticmethod
    def _lookup_month(field, value): return func.extract("month", field) == value
    @staticmethod
    def _lookup_day(field, value): return func.extract("day", field) == value
    @staticmethod
    def _lookup_week_day(field, value): return func.extract("dow", field) + 1 == value
    @staticmethod
    def _lookup_quarter(field, value): return func.extract("quarter", field) == value
    @staticmethod
    def _lookup_date(field, value): return func.cast(field, String).like(f"{value}%")
    
    # Full-text
    @staticmethod
    def _lookup_search(field, value): return field.op("@@")(func.plainto_tsquery("english", value))
    
    # JSON (PostgreSQL)
    @staticmethod
    def _lookup_json_contains(field, value: dict): return field.op("@>")(value)
    @staticmethod
    def _lookup_json_has_key(field, value: str): return field.op("?")(value)


# ========== Q OBJECTS ==========

class Q:
    """Django-style Q objects for complex queries."""
    
    def __init__(self, **lookups):
        self.lookups = lookups
        self.negated = False
        self.connector = "AND"
        self.children = []
    
    def __invert__(self):
        self.negated = not self.negated
        return self
    
    def __and__(self, other):
        new_q = Q()
        new_q.connector = "AND"
        new_q.children = [self, other]
        return new_q
    
    def __or__(self, other):
        new_q = Q()
        new_q.connector = "OR"
        new_q.children = [self, other]
        return new_q
    
    def to_sqlalchemy(self, model, parser):
        conditions = []
        
        if self.lookups:
            conditions.extend(parser.parse(model, **self.lookups))
        
        for child in self.children:
            if isinstance(child, Q):
                conditions.append(child.to_sqlalchemy(model, parser))
            else:
                conditions.append(child)
        
        if not conditions:
            return None
        
        result = and_(*conditions) if self.connector == "AND" else or_(*conditions)
        return not_(result) if self.negated else result


# ========== CRUD BASE ==========

class CRUDBase(Generic[ModelType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model
        self.parser = LookupParser()
    
    # ========== GET ==========
    
    def get(self, db: Session, id: Any) -> Optional[ModelType]:
        """Get by primary key."""
        return db.get(self.model, id)
    
    def get_by(self, db: Session, **lookups) -> Optional[ModelType]:
        """Get single by lookups."""
        conditions = self.parser.parse(self.model, **lookups)
        stmt = select(self.model).where(and_(*conditions))
        return db.execute(stmt).scalar_one_or_none()
    
    def all(self, db: Session, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """List all with pagination."""
        return db.execute(
            select(self.model).offset(skip).limit(limit)
        ).scalars().all()
    
    def filter(self, db: Session, **lookups) -> List[ModelType]:
        """Filter by lookups."""
        conditions = self.parser.parse(self.model, **lookups)
        stmt = select(self.model).where(and_(*conditions))
        return db.execute(stmt).scalars().all()
    
    def exclude(self, db: Session, **lookups) -> List[ModelType]:
        """Exclude by lookups."""
        conditions = self.parser.parse(self.model, **lookups)
        stmt = select(self.model).where(not_(and_(*conditions)))
        return db.execute(stmt).scalars().all()
    
    def complex_filter(self, db: Session, *q_objects: Q, **lookups) -> List[ModelType]:
        """Filter with Q objects + lookups."""
        conditions = []
        
        # Regular lookups (AND)
        if lookups:
            conditions.extend(self.parser.parse(self.model, **lookups))
        
        # Q objects
        for q in q_objects:
            sql_q = q.to_sqlalchemy(self.model, self.parser)
            if sql_q is not None:
                conditions.append(sql_q)
        
        stmt = select(self.model)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        return db.execute(stmt).scalars().all()
    
    def exists(self, db: Session, **lookups) -> bool:
        """Check if record exists."""
        conditions = self.parser.parse(self.model, **lookups) if lookups else []
        stmt = select(func.count()).select_from(self.model)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        return db.execute(stmt).scalar() > 0
    
    def count(self, db: Session, **lookups) -> int:
        """Count records."""
        conditions = self.parser.parse(self.model, **lookups) if lookups else []
        stmt = select(func.count()).select_from(self.model)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        return db.execute(stmt).scalar()
    
    def first(self, db: Session, **lookups) -> Optional[ModelType]:
        """Get first match."""
        conditions = self.parser.parse(self.model, **lookups) if lookups else []
        stmt = select(self.model)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(self.model.id).limit(1)
        return db.execute(stmt).scalar_one_or_none()
    
    def last(self, db: Session, **lookups) -> Optional[ModelType]:
        """Get last match."""
        conditions = self.parser.parse(self.model, **lookups) if lookups else []
        stmt = select(self.model)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(desc(self.model.id)).limit(1)
        return db.execute(stmt).scalar_one_or_none()
    
    def order_by(self, db: Session, *fields: str, **lookups) -> List[ModelType]:
        """Order results. Prefix with '-' for descending."""
        conditions = self.parser.parse(self.model, **lookups) if lookups else []
        stmt = select(self.model)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        order_clauses = []
        for field in fields:
            if field.startswith("-"):
                order_clauses.append(desc(getattr(self.model, field[1:])))
            else:
                order_clauses.append(asc(getattr(self.model, field)))
        
        stmt = stmt.order_by(*order_clauses)
        return db.execute(stmt).scalars().all()
    
    def values_list(self, db: Session, *fields: str, flat: bool = False, **lookups) -> List[Any]:
        """Get list of field values."""
        columns = [getattr(self.model, f) for f in fields]
        conditions = self.parser.parse(self.model, **lookups) if lookups else []
        
        stmt = select(*columns)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        results = db.execute(stmt).all()
        
        if flat and len(fields) == 1:
            return [r[0] for r in results]
        return [tuple(r) for r in results]
    
    def get_with_related(self, db: Session, id: Any, *related: str) -> Optional[ModelType]:
        """Eager load relationships."""
        stmt = select(self.model).where(self.model.id == id)
        for rel in related:
            stmt = stmt.options(selectinload(getattr(self.model, rel)))
        return db.execute(stmt).scalar_one_or_none()
    
    # ========== CREATE ==========
    
    def create(self, db: Session, **kwargs) -> ModelType:
        """Create new record."""
        instance = self.model(**kwargs)
        db.add(instance)
        db.commit()
        db.refresh(instance)
        return instance
    
    def bulk_create(self, db: Session, objects: List[Dict[str, Any]]) -> List[ModelType]:
        """Bulk insert."""
        instances = [self.model(**obj) for obj in objects]
        db.bulk_save_objects(instances)
        db.commit()
        return instances
    
    def get_or_create(self, db: Session, defaults: Dict[str, Any] = None, **lookups) -> Tuple[ModelType, bool]:
        """Get or create."""
        instance = self.get_by(db, **lookups)
        if instance:
            return instance, False
        
        params = {**lookups, **(defaults or {})}
        return self.create(db, **params), True
    
    def update_or_create(self, db: Session, defaults: Dict[str, Any] = None, **lookups) -> Tuple[ModelType, bool]:
        """Update or create."""
        instance = self.get_by(db, **lookups)
        defaults = defaults or {}
        
        if instance:
            for key, value in defaults.items():
                setattr(instance, key, value)
            created = False
        else:
            instance = self.model(**{**lookups, **defaults})
            db.add(instance)
            created = True
        
        db.commit()
        db.refresh(instance)
        return instance, created
    
    # ========== UPDATE ==========
    
    def update(self, db: Session, id: Any, **kwargs) -> Optional[ModelType]:
        """Update by primary key."""
        instance = self.get(db, id)
        if not instance:
            return None
        
        for key, value in kwargs.items():
            setattr(instance, key, value)
        
        db.commit()
        db.refresh(instance)
        return instance
    
    def update_by(self, db: Session, filters: Dict[str, Any], **updates) -> int:
        """Bulk update by filter."""
        conditions = self.parser.parse(self.model, **filters)
        stmt = sql_update(self.model).where(and_(*conditions)).values(**updates)
        result = db.execute(stmt)
        db.commit()
        return result.rowcount
    
    def increment(self, db: Session, id: Any, field: str, amount: Union[int, float] = 1) -> Optional[ModelType]:
        """Atomically increment."""
        instance = self.get(db, id)
        if instance:
            current = getattr(instance, field, 0) or 0
            setattr(instance, field, current + amount)
            db.commit()
            db.refresh(instance)
        return instance
    
    # ========== DELETE ==========
    
    def delete(self, db: Session, id: Any) -> bool:
        """Delete by primary key."""
        instance = self.get(db, id)
        if not instance:
            return False
        
        db.delete(instance)
        db.commit()
        return True
    
    def delete_by(self, db: Session, **lookups) -> int:
        """Bulk delete by lookups."""
        conditions = self.parser.parse(self.model, **lookups)
        stmt = sql_delete(self.model).where(and_(*conditions))
        result = db.execute(stmt)
        db.commit()
        return result.rowcount
    
    def soft_delete(self, db: Session, id: Any, deleted_field: str = "is_deleted") -> Optional[ModelType]:
        """Soft delete."""
        return self.update(db, id, **{deleted_field: True})


# ========== STANDALONE FUNCTIONS ==========

def get(db: Session, model: Type[ModelType], id: Any) -> Optional[ModelType]:
    return db.get(model, id)

def get_by(db: Session, model: Type[ModelType], **lookups) -> Optional[ModelType]:
    parser = LookupParser()
    conditions = parser.parse(model, **lookups)
    stmt = select(model).where(and_(*conditions))
    return db.execute(stmt).scalar_one_or_none()

def filter_query(db: Session, model: Type[ModelType], **lookups) -> List[ModelType]:
    parser = LookupParser()
    conditions = parser.parse(model, **lookups)
    stmt = select(model).where(and_(*conditions))
    return db.execute(stmt).scalars().all()

def create(db: Session, model: Type[ModelType], **kwargs) -> ModelType:
    instance = model(**kwargs)
    db.add(instance)
    db.commit()
    db.refresh(instance)
    return instance

def get_or_create(db: Session, model: Type[ModelType], defaults: Optional[Dict] = None, **lookups) -> Tuple[ModelType, bool]:
    instance = get_by(db, model, **lookups)
    if instance:
        return instance, False
    params = {**lookups, **(defaults or {})}
    return create(db, model, **params), True

def update_or_create(db: Session, model: Type[ModelType], defaults: Optional[Dict] = None, **lookups) -> Tuple[ModelType, bool]:
    instance = get_by(db, model, **lookups)
    defaults = defaults or {}
    
    if instance:
        for k, v in defaults.items():
            setattr(instance, k, v)
        created = False
    else:
        instance = model(**{**lookups, **defaults})
        db.add(instance)
        created = True
    
    db.commit()
    db.refresh(instance)
    return instance, created

def update(db: Session, model: Type[ModelType], id: Any, **kwargs) -> Optional[ModelType]:
    instance = get(db, model, id)
    if instance:
        for k, v in kwargs.items():
            setattr(instance, k, v)
        db.commit()
        db.refresh(instance)
    return instance

def delete(db: Session, model: Type[ModelType], id: Any) -> bool:
    instance = get(db, model, id)
    if instance:
        db.delete(instance)
        db.commit()
        return True
    return False

def exists(db: Session, model: Type[ModelType], **lookups) -> bool:
    parser = LookupParser()
    conditions = parser.parse(model, **lookups)
    stmt = select(func.count()).select_from(model).where(and_(*conditions))
    return db.execute(stmt).scalar() > 0

def count(db: Session, model: Type[ModelType], **lookups) -> int:
    parser = LookupParser()
    conditions = parser.parse(model, **lookups) if lookups else []
    stmt = select(func.count()).select_from(model)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    return db.execute(stmt).scalar()