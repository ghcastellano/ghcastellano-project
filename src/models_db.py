from datetime import date, datetime
from enum import Enum
from typing import Optional, List
import uuid

from sqlalchemy import String, Boolean, ForeignKey, Index, Text, Date, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

# 1. Declaração Base
class Base(DeclarativeBase):
    pass

# 2. Enumerações
class UserRole(str, Enum):
    CONSULTANT = "CONSULTANT"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"

class VisitStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"
    MISSED = "MISSED"

class InspectionStatus(str, Enum):
    PROCESSING = "PROCESSING"
    PENDING_MANAGER_REVIEW = "PENDING_MANAGER_REVIEW" # Aguardando Gestor
    WAITING_APPROVAL = "WAITING_APPROVAL"             # Obsoleto (manter por compatibilidade)
    APPROVED = "APPROVED"                             # Aprovado pelo Gestor, vai para Consultor
    PENDING_VERIFICATION = "PENDING_VERIFICATION"     # Em verificação de campo (Consultor)
    COMPLETED = "COMPLETED"                           # Finalizado
    REJECTED = "REJECTED"

class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class ActionPlanItemStatus(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"

from flask_login import UserMixin

# 3. Tabelas
from sqlalchemy import Table, Column

# Tabela de Associação M2M: Consultor <-> Estabelecimentos
consultant_establishments = Table(
    "consultant_establishments",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True),
    Column("establishment_id", UUID(as_uuid=True), ForeignKey("establishments.id"), primary_key=True),
)

class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    cnpj: Mapped[Optional[str]] = mapped_column(String, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)

    # Relacionamentos
    # establishments (Removido: Company não possui relacionamento direto com Establishment na nova regra)
    users: Mapped[List["User"]] = relationship(back_populates="company")
    establishments: Mapped[List["Establishment"]] = relationship(back_populates="company")

class Establishment(Base):
    __tablename__ = "establishments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # company_id mapping REMOVED (Decoupled)
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("companies.id"), nullable=True) # Mantendo opcional para não quebrar a table existente imediatamente, mas sem uso lógico?
    # Melhor remover a obrigatoriedade da FK se o user pediu "não tem relacionamento".
    # Vou deixar nullable caso precisemos migrar dados, mas a lógica da app vai ignorar.
    
    name: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String) # Código interno ou identificador
    drive_folder_id: Mapped[Optional[str]] = mapped_column(String) # Pasta específica deste estabelecimento
    
    # Novos campos V5 (WhatsApp Integration)
    responsible_name: Mapped[Optional[str]] = mapped_column(String)
    responsible_phone: Mapped[Optional[str]] = mapped_column(String)
    
    # Relacionamento com Contatos (1:N)
    contacts: Mapped[List["Contact"]] = relationship(back_populates="establishment", cascade="all, delete-orphan")
    company: Mapped["Company"] = relationship(back_populates="establishments")
    users: Mapped[List["User"]] = relationship(
        secondary=consultant_establishments,
        back_populates="establishments"
    )
    inspections: Mapped[List["Inspection"]] = relationship(back_populates="establishment")

class Contact(Base):
    __tablename__ = 'contacts'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    establishment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('establishments.id'))
    name: Mapped[str] = mapped_column(String)
    phone: Mapped[str] = mapped_column(String) # WhatsApp
    email: Mapped[Optional[str]] = mapped_column(String)
    role: Mapped[Optional[str]] = mapped_column(String) # Ex: Gerente, Dono
    
    establishment: Mapped["Establishment"] = relationship(back_populates="contacts")

    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)


class User(UserMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String) # Autenticação
    role: Mapped[UserRole] = mapped_column(nullable=False, default=UserRole.CONSULTANT)
    name: Mapped[Optional[str]] = mapped_column(String) # Nome para exibição
    whatsapp: Mapped[Optional[str]] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Novos campos V3
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("companies.id"), nullable=True)
    
    # establishment_id REMOVED (replaced by establishments list)
    # Mantido temporariamente no DB físico se quiser, mas no modelo python vamos remover para usar a lista.
    # Para migração funcionar é melhor comentar o campo mapeado ou deixá-lo deprecated.
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False) 

    # Relacionamentos
    company: Mapped[Optional["Company"]] = relationship(back_populates="users")
    
    # M2M Relationship
    establishments: Mapped[List["Establishment"]] = relationship(
        secondary=consultant_establishments, 
        back_populates="users"
    )
    
    visits: Mapped[List["Visit"]] = relationship(back_populates="consultant")
    approved_plans: Mapped[List["ActionPlan"]] = relationship(back_populates="approved_by")

class Client(Base):
    """
    LEGADO: Mantido temporariamente para migração. 
    Idealmente será substituído por Company.
    """
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    cnpj: Mapped[Optional[str]] = mapped_column(String, unique=True)
    drive_root_folder_id: Mapped[str] = mapped_column(String, nullable=False)
    drive_folder_link: Mapped[Optional[str]] = mapped_column(String)

    # Relacionamentos
    visits: Mapped[List["Visit"]] = relationship(back_populates="client")
    inspections: Mapped[List["Inspection"]] = relationship(back_populates="client")

class Visit(Base):
    __tablename__ = "visits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), nullable=False) # Legado
    consultant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False) 
    status: Mapped[VisitStatus] = mapped_column(default=VisitStatus.SCHEDULED)
    drive_visit_folder_id: Mapped[Optional[str]] = mapped_column(String)

    # Relacionamentos
    client: Mapped["Client"] = relationship(back_populates="visits")
    consultant: Mapped["User"] = relationship(back_populates="visits") 
    inspections: Mapped[List["Inspection"]] = relationship(back_populates="visit")

class Inspection(Base):
    __tablename__ = "inspections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    visit_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("visits.id"), nullable=True)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), nullable=True) # Tornado opcional para V3
    
    # Novo campo V3
    establishment_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("establishments.id"), nullable=True)
    
    drive_file_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    drive_web_link: Mapped[Optional[str]] = mapped_column(String)
    
    # Novo campo V5 (Duplicidade)
    file_hash: Mapped[Optional[str]] = mapped_column(String, index=True)
    
    status: Mapped[InspectionStatus] = mapped_column(default=InspectionStatus.PROCESSING)
    
    # Armazena resposta bruta da IA para auditoria
    ai_raw_response: Mapped[dict] = mapped_column(JSONB, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)

    # Relacionamentos
    client: Mapped["Client"] = relationship(back_populates="inspections")
    establishment: Mapped[Optional["Establishment"]] = relationship(back_populates="inspections")
    visit: Mapped[Optional["Visit"]] = relationship(back_populates="inspections")
    action_plan: Mapped[Optional["ActionPlan"]] = relationship(back_populates="inspection", uselist=False)

class ActionPlan(Base):
    __tablename__ = "action_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inspection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inspections.id"), unique=True, nullable=False)
    
    final_pdf_drive_id: Mapped[Optional[str]] = mapped_column(String)
    final_pdf_public_link: Mapped[Optional[str]] = mapped_column(String)
    
    approved_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    
    # Rich Content (Added in Migration V11)
    summary_text: Mapped[Optional[str]] = mapped_column(Text)
    strengths_text: Mapped[Optional[str]] = mapped_column(Text)
    stats_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True) # Added V11

    # Relacionamentos
    inspection: Mapped["Inspection"] = relationship(back_populates="action_plan")
    approved_by: Mapped[Optional["User"]] = relationship(back_populates="approved_plans")
    items: Mapped[List["ActionPlanItem"]] = relationship(back_populates="action_plan", cascade="all, delete-orphan")

class ActionPlanItem(Base):
    __tablename__ = "action_plan_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action_plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("action_plans.id"), nullable=False)
    
    problem_description: Mapped[str] = mapped_column(Text, nullable=False)
    corrective_action: Mapped[str] = mapped_column(Text, nullable=False)
    legal_basis: Mapped[Optional[str]] = mapped_column(Text)
    deadline_date: Mapped[Optional[date]] = mapped_column(Date)
    
    severity: Mapped[SeverityLevel] = mapped_column(default=SeverityLevel.MEDIUM)
    status: Mapped[ActionPlanItemStatus] = mapped_column(default=ActionPlanItemStatus.OPEN)
    ai_suggested_deadline: Mapped[Optional[str]] = mapped_column(String) # POC compatibility
    
    sector: Mapped[Optional[str]] = mapped_column(Text) # V14 Grouping
    
    manager_notes: Mapped[Optional[str]] = mapped_column(Text) # Notas do gestor

    # Relacionamento Reverso
    action_plan: Mapped["ActionPlan"] = relationship(back_populates="items")


# 4. Job State Machine (Architecture Evolution Phase 12)
class JobStatus(str, Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"

class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Tenant Isolation
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    
    # Metadata
    type: Mapped[str] = mapped_column(String, nullable=False) # 'OCR', 'RAG', 'REPORT'
    status: Mapped[JobStatus] = mapped_column(default=JobStatus.PENDING, index=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    
    # Cost & Observability
    cost_tokens_input: Mapped[int] = mapped_column(default=0)
    cost_tokens_output: Mapped[int] = mapped_column(default=0)
    execution_time_seconds: Mapped[float] = mapped_column(default=0.0)
    cost_input_usd: Mapped[float] = mapped_column(default=0.0)
    cost_output_usd: Mapped[float] = mapped_column(default=0.0)
    cost_input_brl: Mapped[float] = mapped_column(default=0.0)
    cost_output_brl: Mapped[float] = mapped_column(default=0.0)
    api_calls_count: Mapped[int] = mapped_column(default=0)
    attempts: Mapped[int] = mapped_column(default=0)

    # Payloads for Debug/Retry
    input_payload: Mapped[dict] = mapped_column(JSONB, nullable=True)
    result_payload: Mapped[dict] = mapped_column(JSONB, nullable=True)
    error_log: Mapped[Optional[str]] = mapped_column(Text)

    # POC Rich Data
    summary_text = Column(String)
    strengths_text = Column(String) # For comma-separated or text block
    stats_json = Column(JSONB) # For compliance counts

    # Relationships
    company: Mapped["Company"] = relationship()
