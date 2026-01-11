from pydantic import BaseModel, model_validator, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from app.models.case import CaseStatus, RiskLevel, EntryVisibility, EntryType
from app.models.student import Gender

class CaseCreate(BaseModel):
    student_id: UUID = Field(..., description="ID of the student this case is for")
    created_by: UUID = Field(..., description="ID of the user creating the case")
    presenting_concerns: Optional[str] = Field(default=None, description="Initial concerns or reasons for opening the case")
    initial_risk: RiskLevel = Field(default=RiskLevel.LOW, description="Initial risk assessment level")
    
    class Config:
        json_schema_extra = {
            "example": {
                "student_id": "123e4567-e89b-12d3-a456-426614174007",
                "created_by": "123e4567-e89b-12d3-a456-426614174021",
                "presenting_concerns": "Student showing signs of anxiety and social withdrawal over the past 2 weeks. Teacher reports decreased participation in class, avoiding group activities, and appearing withdrawn. Parent contacted school expressing concerns about changes in mood at home. Recent assessment scores indicate elevated depression symptoms (PHQ-9: 11).",
                "initial_risk": "medium"
            }
        }

class CaseUpdate(BaseModel):
    status: Optional[CaseStatus] = Field(default=None, description="Case status")
    risk_level: Optional[RiskLevel] = Field(default=None, description="Risk level assessment")
    tags: Optional[List[str]] = Field(default=None, description="Tags for categorization (e.g., anxiety, depression)")
    assigned_counsellor: Optional[UUID] = Field(default=None, description="ID of assigned counsellor")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "intervention",
                "risk_level": "high",
                "tags": ["anxiety", "social-withdrawal", "academic-stress"],
                "assigned_counsellor": "123e4567-e89b-12d3-a456-426614174020"
            }
        }

class CaseResponse(BaseModel):
    case_id: UUID
    student_id: UUID
    created_by: UUID
    status: CaseStatus
    risk_level: RiskLevel
    tags: Optional[List[str]] = None
    assigned_counsellor: Optional[UUID] = None
    ai_summary: Optional[str] = None
    processed: bool = False
    created_at: datetime
    closed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "case_id": "def45678-e89b-12d3-a456-426614174092",
                "student_id": "123e4567-e89b-12d3-a456-426614174007",
                "created_by": "123e4567-e89b-12d3-a456-426614174021",
                "status": "intervention",
                "risk_level": "medium",
                "tags": ["anxiety", "social-withdrawal", "academic-stress", "depression"],
                "assigned_counsellor": "123e4567-e89b-12d3-a456-426614174021",
                "ai_summary": "15-year-old male student presenting with moderate depression and anxiety symptoms. Recent PHQ-9 score of 11 indicates moderate depression. Teacher observations note social withdrawal and decreased classroom participation over 2-week period. Parent reports similar behavioral changes at home. Academic performance declining. Recommended interventions: weekly counseling sessions, CBT-focused treatment, monitor for escalation, parent involvement.",
                "processed": True,
                "created_at": "2024-10-18T10:30:00Z",
                "closed_at": None
            }
        }

class StudentInfo(BaseModel):
    student_id: Optional[UUID] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    display_name: Optional[str] = None
    email: Optional[str] = None
    school_id: Optional[UUID] = None
    # Legacy fields (from old Student model - kept for backward compatibility)
    gender: Optional[Gender] = None
    class_id: Optional[UUID] = None
    class_name: Optional[str] = None
    parents_id: Optional[List[UUID]] = None

    class Config:
        from_attributes = True

class ParentInfo(BaseModel):
    user_id: UUID
    display_name: str
    email: str
    phone: Optional[str] = None

    class Config:
        from_attributes = True

class TeacherInfo(BaseModel):
    user_id: UUID
    display_name: str
    email: str
    phone: Optional[str] = None

    class Config:
        from_attributes = True

class CounsellorInfo(BaseModel):
    user_id: UUID
    display_name: str
    email: str
    phone: Optional[str] = None

    class Config:
        from_attributes = True

class CaseDetailResponse(BaseModel):
    case: CaseResponse
    student: StudentInfo
    teacher: Optional[TeacherInfo] = None
    counsellor: Optional[CounsellorInfo] = None
    parents: List[ParentInfo] = []

    class Config:
        json_schema_extra = {
            "example": {
                "case": {
                    "case_id": "def45678-e89b-12d3-a456-426614174092",
                    "student_id": "123e4567-e89b-12d3-a456-426614174007",
                    "created_by": "123e4567-e89b-12d3-a456-426614174021",
                    "status": "intervention",
                    "risk_level": "medium",
                    "tags": ["anxiety", "social-withdrawal", "academic-stress", "depression"],
                    "assigned_counsellor": "123e4567-e89b-12d3-a456-426614174021",
                    "ai_summary": "15-year-old male student presenting with moderate depression and anxiety symptoms. Recent PHQ-9 score of 11 indicates moderate depression.",
                    "processed": True,
                    "created_at": "2024-10-18T10:30:00Z",
                    "closed_at": None
                },
                "student": {
                    "student_id": "123e4567-e89b-12d3-a456-426614174007",
                    "first_name": "Ethan",
                    "last_name": "Lopez",
                    "display_name": "Ethan Lopez",
                    "email": "ethan.lopez@school.edu",
                    "school_id": "8f3c4567-e89b-12d3-a456-426614174033"
                },
                "teacher": {
                    "user_id": "abc12345-e89b-12d3-a456-426614174055",
                    "display_name": "Ms. Sarah Johnson",
                    "email": "sarah.johnson@lincolnhs.edu",
                    "phone": "+1-555-0145"
                },
                "counsellor": {
                    "user_id": "123e4567-e89b-12d3-a456-426614174021",
                    "display_name": "Dr. David Chen",
                    "email": "david.chen@lincolnhs.edu",
                    "phone": "+1-555-0123"
                },
                "parents": [
                    {
                        "user_id": "9a2b3c4d-e89b-12d3-a456-426614174045",
                        "display_name": "Maria Lopez",
                        "email": "maria.lopez@email.com",
                        "phone": "+1-555-0189"
                    }
                ]
            }
        }

class JournalEntryCreate(BaseModel):
    case_id: UUID = Field(..., description="ID of the case this entry belongs to")
    author_id: UUID = Field(..., description="ID of the user creating the entry")
    visibility: EntryVisibility = Field(default=EntryVisibility.SHARED, description="Who can view this entry")
    type: EntryType = Field(..., description="Type of journal entry")
    content: Optional[str] = Field(default=None, description="Text content of the entry")
    audio_url: Optional[str] = Field(default=None, description="URL to audio recording")
    
    @model_validator(mode='after')
    def check_content_or_audio(self):
        if not self.content and not self.audio_url:
            raise ValueError('At least one of content or audio_url must be provided')
        return self
    
    class Config:
        json_schema_extra = {
            "example": {
                "case_id": "def45678-e89b-12d3-a456-426614174092",
                "author_id": "123e4567-e89b-12d3-a456-426614174021",
                "visibility": "shared",
                "type": "session_note",
                "content": "Session 3 - 45 minutes. Student opened up more about academic pressures and social concerns. Discussed cognitive restructuring techniques for negative thought patterns. Practiced deep breathing exercises. Student reported trying homework from last session and found it somewhat helpful. Assigned: Continue daily mood journaling and practice breathing exercises when feeling overwhelmed. Progress noted in student's willingness to engage. Plan to involve parents in next session to discuss support strategies at home.",
                "audio_url": None
            }
        }

class JournalEntryResponse(BaseModel):
    entry_id: UUID
    case_id: UUID
    author_id: UUID
    author_name: str
    visibility: EntryVisibility
    type: EntryType
    content: Optional[str] = None
    audio_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "entry_id": "5e6f7890-e89b-12d3-a456-426614174099",
                "case_id": "def45678-e89b-12d3-a456-426614174092",
                "author_id": "123e4567-e89b-12d3-a456-426614174021",
                "author_name": "Dr. David Chen",
                "visibility": "shared",
                "type": "session_note",
                "content": "Session 3 - 45 minutes. Student opened up more about academic pressures and social concerns. Progress noted in student's willingness to engage and practice coping strategies.",
                "audio_url": None,
                "created_at": "2024-10-22T14:30:00Z"
            }
        }
