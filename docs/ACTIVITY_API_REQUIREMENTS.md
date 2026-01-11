# Activity API Requirements Document

## Overview

The B2B Activity API provides endpoints for managing educational activities, assignments, submissions, and progress tracking. The system integrates with a separate Activity Engine database for curated/generated activity content and maintains its own database for assignments and submissions.

---

## Architecture

### Services
1. **B2B Service** (Port 8000) - Assignments, submissions, comments, analytics
2. **Activity Engine** (Port 8002) - Activity content, proofs, rankings, user progress

### Databases
1. **B2B Database** - Stores assignments, submissions, comments, and user-created activities
2. **Activity Engine Database** - Stores curated and AI-generated activity content with JSONB data

### Key Models

| Model | Table | Purpose |
|-------|-------|---------|
| `Activity` | `b2b_activities` | User-created activities within schools |
| `ActivityData` | `activities` | Curated activities from Activity Engine |
| `GeneratedActivityData` | `generatedactivities` | AI-generated activities |
| `ActivityAssignment` | `b2b_activity_assignments` | Activity assignments to classes |
| `ActivitySubmission` | `b2b_activity_submissions` | Student submissions |
| `SubmissionComment` | `b2b_submission_comments` | Comments on submissions |

---

## API Endpoints

### 1. Activities (Content)

#### GET `/api/v1/activities/`
Fetch activities with filtering from Activity Engine database.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `skip` | int | No | Pagination offset (default: 0) |
| `limit` | int | No | Max results (default: 100) |
| `age` | int | No | Filter by exact age |
| `diagnosis` | string | No | Filter by diagnosis (case-insensitive partial match) |
| `themes` | string | No | Comma-separated themes filter |
| `source` | enum | No | `all`, `curated`, or `generated` (default: all) |
| `include_flashcards` | bool | No | Include S3 flashcard images (default: false) |

**Response:**
```json
{
  "filters": {
    "age": 8,
    "diagnosis": "ADHD",
    "themes": ["Emotional Regulation"],
    "source": "all"
  },
  "total_count": 150,
  "count": 100,
  "activities": [
    {
      "id": 1,
      "activity_id": "ACT_001",
      "activity_name": "Mindful Breathing",
      "framework": "SEL",
      "age": 8,
      "diagnosis": "ADHD, Anxiety",
      "cognitive": "Focus",
      "sensory": "Auditory",
      "themes": "Emotional Regulation",
      "setting": "Classroom",
      "supervision": "Teacher",
      "duration_pref": "15 mins",
      "risk_level": "Low",
      "skill_level": "Beginner",
      "activity_data": { /* JSONB content */ },
      "thumbnail_url": "https://s3.../thumbnail.png",
      "source": "curated",
      "flashcards": null
    }
  ]
}
```

#### GET `/api/v1/activities/{activity_id}`
Get single activity by ID.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `include_flashcards` | bool | No | Include S3 flashcard images |

**Response:** Single activity object (same structure as list item)

---

## Activity Engine Endpoints (Port 8002)

### 1. Activities (`/api/v1/activities`)

#### GET `/api/v1/activities`
Get list of activities with user-specific completion status.

**Headers:**
```
x-user-id: <user_id>
x-role: B2C_USER | B2B_STUDENT | B2B_TEACHER | SUPER_ADMIN
```

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `skip` | int | No | Pagination offset (default: 0) |
| `limit` | int | No | Max results (default: 100) |
| `age` | int | No | Filter by age |
| `diagnosis` | string | No | Filter by diagnosis |
| `themes` | string | No | Comma-separated themes |
| `framework` | string | No | Filter by framework |
| `level` | string | No | Filter by skill level |
| `search` | string | No | Search query |
| `source` | enum | No | `all`, `curated`, `generated` |
| `include_flashcards` | bool | No | Include flashcard URLs |

**Response:**
```json
{
  "filters": {
    "age": 8,
    "diagnosis": "ADHD",
    "themes": ["emotional regulation"],
    "source": "all"
  },
  "total_count": 150,
  "count": 100,
  "activities": [
    {
      "id": 1,
      "activity_id": "ACT_001",
      "activity_name": "Mindful Breathing",
      "framework": "SEL",
      "age": 8,
      "diagnosis": "ADHD, Anxiety",
      "cognitive": "Focus",
      "sensory": "Auditory",
      "themes": "Emotional Regulation",
      "setting": "Classroom",
      "supervision": "Teacher",
      "duration_pref": "15 mins",
      "risk_level": "Low",
      "skill_level": "Beginner",
      "activity_data": { /* JSONB content */ },
      "thumbnail_url": "https://s3.../presigned-url",
      "source": "curated",
      "flashcards": null,
      "is_completed": false,
      "score": 0,
      "user_proof": null,
      "status": "PENDING"
    }
  ]
}
```

#### GET `/api/v1/activities/{activity_id}`
Get activity detail with flashcards and user proof.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `include_flashcards` | bool | No | Include flashcard URLs (default: true) |

**Response:** Activity object with:
- `flashcards`: Array of presigned S3 URLs for flashcard images
- `user_proof`: Presigned URL for user's uploaded proof (if exists)
- `is_completed`: Boolean indicating completion status
- `status`: "PENDING" or "COMPLETED"
- `score`: User's score for this activity

#### POST `/api/v1/activities/{activity_id}/proof`
Upload proof for an activity.

**Restrictions:** Teachers cannot upload proofs

**Content-Type:** `multipart/form-data`

**Form Fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | Yes | Proof file (png, jpg, jpeg, mp4, avi, mov, webm) |

**Response:**
```json
{
  "proof_url": "https://s3.../presigned-url",
  "status": "PENDING"
}
```

#### POST `/api/v1/activities/{activity_id}/complete`
Complete an activity (requires proof to be uploaded first).

**Restrictions:** Teachers cannot complete activities

**Response:**
```json
{
  "activity_id": "ACT_001",
  "final_score": 100,
  "completed_at": "2026-01-03T14:30:00Z"
}
```

---

### 2. User Progress (`/api/v1/me`)

#### GET `/api/v1/me/summary`
Get current user's progress summary.

**Available to:** B2C_USER, B2B_STUDENT

**Response:**
```json
{
  "total_completed": 12,
  "total_score": 1200
}
```

---

### 3. Rankings (`/api/v1/classes`)

#### GET `/api/v1/classes/{class_id}/rankings`
Get class rankings by score.

**Available to:**
- B2B_STUDENT (for their own class)
- B2B_TEACHER (for their classes)

**Response:**
```json
[
  {
    "user_id": "student-uuid-1",
    "total_score": 1500,
    "rank": 1
  },
  {
    "user_id": "student-uuid-2",
    "total_score": 1200,
    "rank": 2
  }
]
```

---

### 4. Teacher Endpoints (`/api/v1/teacher`)

#### GET `/api/v1/teacher/classes/{class_id}/students`
Get student progress for a class.

**Available to:** B2B_TEACHER (for their own classes)

**Response:**
```json
[
  {
    "student_id": "student-uuid",
    "completed_count": 12,
    "total_score": 1200,
    "rank": 1
  }
]
```

#### GET `/api/v1/teacher/students/{student_id}/activities`
Get student's activities with proof URLs.

**Available to:** B2B_TEACHER

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `class_id` | string | No | Filter by class (validates teacher access) |

**Response:**
```json
[
  {
    "activity_id": "ACT_001",
    "status": "COMPLETED",
    "proof_url": "https://s3.../presigned-url",
    "score": 100
  }
]
```

---

### 5. Admin Endpoints (`/api/v1/admin`)

**All admin endpoints require:** `x-role: SUPER_ADMIN`

#### POST `/api/v1/admin/activities`
Create a new activity.

**Request Body:**
```json
{
  "activity_id": "ACT_NEW_001",
  "activity_name": "New Activity",
  "framework": "SEL",
  "age": 8,
  "diagnosis": "ADHD",
  "cognitive": "Focus",
  "sensory": "Visual",
  "themes": "Emotional Regulation, Self-Awareness",
  "setting": "Classroom",
  "supervision": "Teacher",
  "duration_pref": "15 mins",
  "risk_level": "Low",
  "skill_level": "Beginner",
  "activity_data": {
    "Description": "...",
    "Instructions": ["..."],
    "Materials": ["..."]
  }
}
```

**Response:** Created activity object with `id` and `created_at`

#### PUT `/api/v1/admin/activities/{activity_id}`
Update an activity.

**Request Body:** Partial activity object (only fields to update)

**Response:** Updated activity object

#### DELETE `/api/v1/admin/activities/{activity_id}`
Delete an activity.

**Response:**
```json
{
  "message": "Activity deleted successfully"
}
```

#### POST `/api/v1/admin/activities/{activity_id}/flashcards`
Batch upload flashcard images for an activity.

**Content-Type:** `multipart/form-data`

**Form Fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `files` | File[] | Yes | Multiple flashcard images |

**Response:**
```json
{
  "message": "Uploaded 5 flashcards",
  "paths": [
    "flashcards/ACT_001/1.png",
    "flashcards/ACT_001/2.png"
  ]
}
```

#### POST `/api/v1/admin/activities/{activity_id}/thumbnail`
Upload thumbnail for an activity.

**Content-Type:** `multipart/form-data`

**Form Fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | Yes | Thumbnail image |

**Response:**
```json
{
  "message": "Thumbnail uploaded successfully",
  "path": "thumbnails/ACT_001.png"
}
```

---

## Activity Engine Models

### ActivitySubmission
```sql
CREATE TABLE activity_submissions (
    submission_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    activity_id VARCHAR NOT NULL,
    user_id VARCHAR NOT NULL,
    proof_s3_path VARCHAR,
    status VARCHAR DEFAULT 'PENDING',  -- PENDING, COMPLETED
    score INTEGER DEFAULT 0,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);
```

### UserStats
```sql
CREATE TABLE user_stats (
    user_id VARCHAR PRIMARY KEY,
    total_completed INTEGER DEFAULT 0,
    total_score INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);
```

### Class & ClassStudent
```sql
CREATE TABLE classes (
    class_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    teacher_id VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE class_students (
    class_id UUID REFERENCES classes(class_id),
    student_id VARCHAR NOT NULL,
    joined_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (class_id, student_id)
);
```

---

### 2. Activity Assignments

#### GET `/api/v1/activity-assignments/dashboard/stats`
Get teacher dashboard statistics.

**Headers:** Requires authentication

**Response:**
```json
{
  "active_assignments": 12,
  "pending_reviews": 5,
  "total_students": 45,
  "classes": [
    {
      "class_id": "uuid",
      "name": "Grade 3A",
      "student_count": 25,
      "active_activity_count": 4
    }
  ]
}
```

#### POST `/api/v1/activity-assignments/assignments`
Create a new activity assignment.

**Headers:** Requires authentication

**Request Body:**
```json
{
  "activity_id": "uuid",
  "class_id": "uuid",
  "due_date": "2026-01-15T00:00:00Z"  // optional
}
```

**Response:**
```json
{
  "assignment_id": "uuid",
  "activity_id": "uuid",
  "class_id": "uuid",
  "due_date": "2026-01-15T00:00:00Z",
  "status": "ACTIVE",
  "created_at": "2026-01-03T10:00:00Z",
  "submission_count": 0,
  "total_students": 25
}
```

**Side Effects:** Creates `PENDING` submission records for all students in the class.

#### GET `/api/v1/activity-assignments/assignments/class/{class_id}`
Get all assignments for a class.

**Response:** Array of assignment objects with activity details and submission counts.

---

### 3. Submissions

#### GET `/api/v1/activity-assignments/submissions/assignment/{assignment_id}`
Get all submissions for an assignment (Teacher view).

**Response:**
```json
[
  {
    "submission_id": "uuid",
    "student_id": "uuid",
    "student_name": "John Doe",
    "file_url": "https://storage.../proof.jpg",
    "status": "SUBMITTED",
    "submitted_at": "2026-01-03T14:30:00Z",
    "feedback": null
  }
]
```

#### GET `/api/v1/activity-assignments/submissions/student/{student_id}`
Get all submissions for a student.

#### POST `/api/v1/activity-assignments/submissions`
Submit activity proof (Student).

**Content-Type:** `multipart/form-data`

**Form Fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `assignment_id` | UUID | Yes | Assignment ID |
| `student_id` | UUID | Yes | Student ID |
| `file` | File | Yes | Proof image/video |

**Response:** Updated submission object

#### PUT `/api/v1/activity-assignments/submissions/{submission_id}`
Review a submission (Teacher).

**Headers:** Requires authentication

**Request Body:**
```json
{
  "status": "VERIFIED",  // VERIFIED or REJECTED
  "feedback": "Great work!"
}
```

---

### 4. Comments

#### GET `/api/v1/activity-assignments/submissions/{submission_id}/comments`
Get all comments for a submission.

**Response:**
```json
[
  {
    "comment_id": "uuid",
    "submission_id": "uuid",
    "user_id": "uuid",
    "student_id": null,
    "message": "Please add more detail",
    "created_at": "2026-01-03T15:00:00Z",
    "sender_name": "Jane Smith"
  }
]
```

#### POST `/api/v1/activity-assignments/submissions/{submission_id}/comments`
Add a comment to a submission.

**Headers:** Requires authentication

**Request Body:**
```json
{
  "message": "Great progress!"
}
```

---

## Activity Engine Roles

| Role | Description | Permissions |
|------|-------------|-------------|
| `B2C_USER` | Consumer user | View activities, upload proofs, complete activities, view own summary |
| `B2B_STUDENT` | School student | Same as B2C_USER + view class rankings |
| `B2B_TEACHER` | School teacher | View activities, view class students, view student activities, view class rankings |
| `SUPER_ADMIN` | Administrator | Full access including CRUD operations on activities |

---

## Enums

### AssignmentStatus
- `ACTIVE` - Assignment is active
- `ARCHIVED` - Assignment is archived

### SubmissionStatus
- `PENDING` - Not yet submitted
- `SUBMITTED` - Submitted, awaiting review
- `VERIFIED` - Approved by teacher
- `REJECTED` - Rejected by teacher

### FileType
- `IMAGE`
- `VIDEO`
- `OTHER`

### ActivityType (B2B Activities)
- `PHYSICAL_DEVELOPMENT`
- `COGNITIVE_DEVELOPMENT`
- `SOCIAL_EMOTIONAL_DEVELOPMENT`
- `LANGUAGE_COMMUNICATION_DEVELOPMENT`

### LocationType
- `IN_CLASS`
- `AT_HOME`
- `OTHER`

### RiskLevel
- `LOW`
- `MEDIUM`
- `HIGH`

### SkillLevel
- `BEGINNER`
- `INTERMEDIATE`
- `ADVANCED`

---

## Activity Data Structure (JSONB)

The `activity_data` field contains rich activity content:

```json
{
  "Description": "Activity description text",
  "Therapy Goal": "Improve emotional regulation",
  "Learning Goal": "Identify emotions",
  "Themes": ["Emotional Regulation", "Self-Awareness"],
  "Materials": ["Paper", "Crayons", "Timer"],
  "Safety Requirements": ["Adult supervision required"],
  "Instructions": [
    "Step 1: Gather materials",
    "Step 2: Explain the activity",
    "Step 3: Begin exercise"
  ],
  "Success Criteria": ["Student completes all steps", "Student can identify 3 emotions"],
  "Duration": "15 minutes",
  "Age Band": "6-8",
  "Facilitator": "Teacher",
  "Environment Setting": "Classroom",
  "Elements": ["Visual", "Kinesthetic"],
  "Activity Type": "Group",
  "Cognitive": "Focus, Memory",
  "Sensory": "Visual, Tactile",
  "Framework": "SEL"
}
```

---

## Frontend Integration

### Headers Required
```typescript
{
  'Content-Type': 'application/json',
  'x-user-id': 'user-uuid',
  'x-role': 'B2B_TEACHER'  // Mapped from B2B roles
}
```

### Role Mapping
| B2B Role | Activity Engine Role |
|----------|---------------------|
| COUNSELLOR | B2B_TEACHER |
| TEACHER | B2B_TEACHER |
| PRINCIPAL | B2B_TEACHER |
| PARENT | B2C_USER |
| CLINICIAN | B2B_TEACHER |
| ADMIN | SUPER_ADMIN |
| STUDENT | B2B_STUDENT |

---

## Missing/Required Endpoints

Based on frontend service analysis, the following endpoints need implementation:

### Activity Engine Endpoints (Port 8002)
1. `POST /api/v1/activities/{activity_id}/proof` - Upload proof
2. `POST /api/v1/activities/{activity_id}/complete` - Complete activity
3. `GET /api/v1/me/summary` - User progress summary
4. `GET /api/v1/classes/{class_id}/rankings` - Class rankings
5. `GET /api/v1/teacher/classes/{class_id}/students` - Teacher class students
6. `GET /api/v1/teacher/students/{student_id}/activities` - Student activities
7. `POST /api/v1/admin/activities` - Create activity (Admin)
8. `PUT /api/v1/admin/activities/{activity_id}` - Update activity (Admin)
9. `DELETE /api/v1/admin/activities/{activity_id}` - Delete activity (Admin)
10. `POST /api/v1/admin/activities/{activity_id}/flashcards` - Upload flashcards
11. `POST /api/v1/admin/activities/{activity_id}/thumbnail` - Upload thumbnail

---

## Database Schema

### b2b_activities
```sql
CREATE TABLE b2b_activities (
    activity_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    school_id UUID REFERENCES b2b_schools(school_id),
    title VARCHAR(200) NOT NULL,
    description TEXT,
    type VARCHAR(50) NOT NULL,
    thumbnail_url VARCHAR,
    duration INTEGER,
    target_grades VARCHAR[],
    materials VARCHAR[],
    instructions TEXT[],
    objectives VARCHAR[],
    diagnosis VARCHAR[],
    location VARCHAR(20),
    risk_level VARCHAR(10),
    skill_level VARCHAR(20),
    theme VARCHAR[],
    is_counselor_only BOOLEAN DEFAULT FALSE,
    created_by UUID NOT NULL REFERENCES b2b_users(user_id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### b2b_activity_assignments
```sql
CREATE TABLE b2b_activity_assignments (
    assignment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    activity_id UUID NOT NULL REFERENCES b2b_activities(activity_id),
    class_id UUID NOT NULL REFERENCES b2b_classes(class_id),
    assigned_by UUID NOT NULL REFERENCES b2b_users(user_id),
    due_date TIMESTAMP,
    status VARCHAR(20) DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT NOW()
);
```

### b2b_activity_submissions
```sql
CREATE TABLE b2b_activity_submissions (
    submission_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assignment_id UUID NOT NULL REFERENCES b2b_activity_assignments(assignment_id),
    student_id UUID NOT NULL REFERENCES b2b_students(student_id),
    file_url VARCHAR,
    file_type VARCHAR(10),
    status VARCHAR(20) DEFAULT 'PENDING',
    feedback TEXT,
    submitted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### b2b_submission_comments
```sql
CREATE TABLE b2b_submission_comments (
    comment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    submission_id UUID NOT NULL REFERENCES b2b_activity_submissions(submission_id),
    user_id UUID REFERENCES b2b_users(user_id),
    student_id UUID REFERENCES b2b_students(student_id),
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

---

## Activity Analytics Endpoints

### 5. Activity Analytics (`/api/v1/analytics`)

#### GET `/api/v1/analytics/activities/{activity_id}`
Get comprehensive analytics for a single activity.

**Response:**
```json
{
  "success": true,
  "data": {
    "activity_id": "uuid",
    "activity_name": "Mindful Breathing",
    "description": "...",
    "type": "SOCIAL_EMOTIONAL_DEVELOPMENT",
    "duration": 15,
    "target_grades": ["3", "4"],
    "themes": ["Emotional Regulation"],
    "diagnosis": ["ADHD"],
    "objectives": ["..."],
    "materials": ["..."],
    "instructions": ["..."],
    "location": "IN_CLASS",
    "risk_level": "LOW",
    "skill_level": "BEGINNER",
    "thumbnail_url": "https://...",
    "is_counselor_only": false,
    "total_assignments": 5,
    "submission_metrics": {
      "total_expected": 125,
      "total_completed": 98,
      "completion_rate": 78.4,
      "verified_count": 85,
      "pending_review": 13
    },
    "status_distribution": {
      "PENDING": 27,
      "SUBMITTED": 13,
      "VERIFIED": 85,
      "REJECTED": 0
    },
    "class_breakdown": [
      {
        "assignment_id": "uuid",
        "class_id": "uuid",
        "class_name": "Grade 3A",
        "assigned_at": "2026-01-01T10:00:00Z",
        "due_date": "2026-01-15T00:00:00Z",
        "total_students": 25,
        "completed": 20,
        "completion_rate": 80.0
      }
    ],
    "submission_timeline": [
      {"date": "2026-01-02", "count": 5},
      {"date": "2026-01-03", "count": 12}
    ]
  }
}
```

#### GET `/api/v1/analytics/students/{student_id}/activities`
Get comprehensive activity analytics for a single student.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `class_id` | UUID | No | Filter by class |
| `status` | string | No | Filter by status: PENDING, SUBMITTED, VERIFIED, REJECTED |
| `days` | int | No | Filter to last N days |

**Response:**
```json
{
  "success": true,
  "data": {
    "student_id": "uuid",
    "student_name": "John Doe",
    "class_id": "uuid",
    "overall_metrics": {
      "total_assigned": 15,
      "total_completed": 12,
      "completion_rate": 80.0,
      "verified_count": 10,
      "rejected_count": 1,
      "pending_count": 3
    },
    "status_distribution": {
      "PENDING": 3,
      "SUBMITTED": 1,
      "VERIFIED": 10,
      "REJECTED": 1
    },
    "activity_type_distribution": [
      {"type": "SOCIAL_EMOTIONAL_DEVELOPMENT", "count": 8, "percentage": 53.3},
      {"type": "COGNITIVE_DEVELOPMENT", "count": 7, "percentage": 46.7}
    ],
    "theme_distribution": [
      {"theme": "Emotional Regulation", "count": 5},
      {"theme": "Focus", "count": 4}
    ],
    "weekly_completion_trend": [
      {"week_of": "2025-12-30", "completed": 3},
      {"week_of": "2026-01-06", "completed": 5}
    ],
    "recent_submissions": [
      {
        "submission_id": "uuid",
        "activity": {
          "activity_id": "uuid",
          "activity_name": "Mindful Breathing",
          "description": "...",
          "type": "SOCIAL_EMOTIONAL_DEVELOPMENT",
          "duration": 15,
          "themes": ["Emotional Regulation"],
          "diagnosis": ["ADHD"],
          "objectives": ["..."],
          "location": "IN_CLASS",
          "risk_level": "LOW",
          "skill_level": "BEGINNER",
          "thumbnail_url": "https://..."
        },
        "status": "VERIFIED",
        "submitted_at": "2026-01-03T14:30:00Z",
        "feedback": "Great work!",
        "due_date": "2026-01-15T00:00:00Z",
        "assigned_at": "2026-01-01T10:00:00Z"
      }
    ]
  }
}
```

#### GET `/api/v1/analytics/students/{student_id}/summary`
Get combined summary of assessment and activity analytics for a student.

**Response:**
```json
{
  "success": true,
  "data": {
    "student_id": "uuid",
    "student_name": "John Doe",
    "class_id": "uuid",
    "risk_level": "low",
    "wellbeing_score": 75,
    "assessments": {
      "total_completed": 5,
      "average_score": 82.5,
      "last_assessment": "2026-01-02T10:00:00Z"
    },
    "activities": {
      "total_assigned": 15,
      "total_completed": 12,
      "completion_rate": 80.0,
      "status_breakdown": {
        "PENDING": 3,
        "SUBMITTED": 1,
        "VERIFIED": 10,
        "REJECTED": 1
      }
    }
  }
}
```

---

### 6. Teacher Analytics (`/api/v1/teacher-analytics`)

#### GET `/api/v1/teacher-analytics/overview`
Get aggregated analytics for all classes assigned to a teacher.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `teacher_id` | UUID | Yes | Teacher ID |
| `days` | int | No | Number of days (default: 30) |

**Response:**
```json
{
  "success": true,
  "data": {
    "teacher_id": "uuid",
    "teacher_name": "Jane Smith",
    "period": {
      "start_date": "2025-12-04",
      "end_date": "2026-01-03",
      "days": 30
    },
    "summary": {
      "total_students": 75,
      "total_classes": 3,
      "avg_wellbeing_score": 72.5,
      "avg_activity_completion": 78.4,
      "avg_daily_streak": 5.2,
      "total_app_openings": 450
    },
    "risk_distribution": {
      "low": 60,
      "medium": 12,
      "high": 3
    },
    "engagement": {
      "total_app_openings": 450,
      "total_assessments_completed": 120,
      "total_activities_completed": 280
    },
    "top_performers": [
      {
        "student_id": "uuid",
        "student_name": "Alice Johnson",
        "class_name": "Grade 3A",
        "daily_streak": 15,
        "wellbeing_score": 92
      }
    ],
    "at_risk_students": [
      {
        "student_id": "uuid",
        "student_name": "Bob Smith",
        "class_name": "Grade 3B",
        "wellbeing_score": 45,
        "risk_level": "high",
        "last_active": "2025-12-28T00:00:00Z"
      }
    ]
  }
}
```

#### GET `/api/v1/teacher-analytics/classes`
Get list of classes assigned to teacher with analytics metrics.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `teacher_id` | UUID | Yes | Teacher ID |
| `search` | string | No | Search by class name |
| `days` | int | No | Number of days (default: 30) |

#### GET `/api/v1/teacher-analytics/classes/{class_id}`
Get detailed analytics for a specific class.

#### GET `/api/v1/teacher-analytics/students`
Get paginated list of all students from teacher's classes.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `teacher_id` | UUID | Yes | Teacher ID |
| `class_id` | UUID | No | Filter by class |
| `search` | string | No | Search by student name |
| `risk_level` | string | No | Filter: low, medium, high |
| `days` | int | No | Number of days (default: 30) |
| `page` | int | No | Page number (default: 1) |
| `limit` | int | No | Items per page (default: 20) |

#### GET `/api/v1/teacher-analytics/students/{student_id}/activities`
Get activity history for a specific student.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `status` | string | No | Filter by status |
| `days` | int | No | Filter to last N days |

**Response:**
```json
{
  "success": true,
  "data": {
    "student_id": "uuid",
    "student_name": "John Doe",
    "total_activities": 15,
    "status_breakdown": {
      "pending": 3,
      "submitted": 1,
      "verified": 10,
      "rejected": 1
    },
    "activities": [
      {
        "submission_id": "uuid",
        "activity_id": "uuid",
        "activity_title": "Mindful Breathing",
        "activity_type": "SOCIAL_EMOTIONAL_DEVELOPMENT",
        "assigned_at": "2026-01-01T10:00:00Z",
        "due_date": "2026-01-15T00:00:00Z",
        "submitted_at": "2026-01-03T14:30:00Z",
        "status": "VERIFIED",
        "feedback": "Great work!",
        "file_url": "https://..."
      }
    ]
  }
}
```

#### GET `/api/v1/teacher-analytics/students/{student_id}/assessments`
Get assessment history for a specific student.

---

### 7. Counsellor Analytics (`/api/v1/counsellor-analytics`)

#### GET `/api/v1/counsellor-analytics/overview`
School-wide aggregated analytics.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `school_id` | UUID | Yes | School ID |
| `days` | int | No | Number of days (default: 30) |

#### GET `/api/v1/counsellor-analytics/classes`
Analytics for all classes in school.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `school_id` | UUID | Yes | School ID |
| `teacher_id` | UUID | No | Filter by teacher |
| `search` | string | No | Search by class name |
| `grade` | string | No | Filter by grade |
| `days` | int | No | Number of days (default: 30) |

**Response includes per class:**
- Student count and risk distribution
- Assessment completion (rate, done, total)
- Activity completion (rate, done, total)
- Webinar attendance (rate, done, total)

#### GET `/api/v1/counsellor-analytics/classes/{class_id}`
Detailed analytics for a specific class.

#### GET `/api/v1/counsellor-analytics/students`
Paginated student list with comprehensive analytics.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `school_id` | UUID | Yes | School ID |
| `class_id` | UUID | No | Filter by class |
| `search` | string | No | Search by student name |
| `risk_level` | string | No | Filter: low, medium, high |
| `days` | int | No | Number of days (default: 30) |
| `page` | int | No | Page number (default: 1) |
| `limit` | int | No | Items per page (default: 20) |

**Response per student includes:**
- Wellbeing score and risk level
- Daily/max streak and last active date
- Assessments completed/total
- Activities completed/total
- Webinars attended/total
- App openings count

#### GET `/api/v1/counsellor-analytics/students/{student_id}/activities`
Student activity history (same as teacher analytics).

#### GET `/api/v1/counsellor-analytics/students/{student_id}/assessments`
Student assessment history with optional response details.

---

## Analytics Response Wrapper

All analytics endpoints return responses wrapped in a standard format:

```json
{
  "success": true,
  "data": { /* endpoint-specific data */ },
  "message": null
}
```

---

## Error Responses

All endpoints return standard error format:

```json
{
  "detail": "Error message description"
}
```

### Common HTTP Status Codes
- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `422` - Validation Error
- `500` - Internal Server Error

---

## Analytics Metrics Summary

### Activity Metrics Tracked
| Metric | Description |
|--------|-------------|
| `total_assigned` | Total activities assigned to student/class |
| `total_completed` | Activities with status SUBMITTED, VERIFIED, or REJECTED |
| `completion_rate` | Percentage of completed vs assigned |
| `verified_count` | Activities approved by teacher |
| `rejected_count` | Activities rejected by teacher |
| `pending_count` | Activities not yet submitted |
| `pending_review` | Submitted but not yet reviewed |

### Engagement Metrics
| Metric | Description |
|--------|-------------|
| `daily_streak` | Current consecutive days of activity |
| `max_streak` | Highest streak achieved |
| `last_active` | Last activity date |
| `app_openings` | Number of app sessions |
| `avg_session_time` | Average session duration in minutes |

### Risk Distribution
| Level | Description |
|-------|-------------|
| `low` | Students with LOW risk level |
| `medium` | Students with MEDIUM risk level |
| `high` | Students with HIGH or CRITICAL risk level |

### Time-Based Analytics
- **Weekly completion trend**: Aggregated by week start date
- **Submission timeline**: Daily submission counts
- **Period filtering**: Configurable via `days` parameter (7, 30, 90, 365)

---

## S3 Storage Structure

```
bucket/
├── master/
│   └── thumbnails/
│       └── {activity_id}.png
├── flashcards/
│   └── {activity_id}/
│       ├── 1.png
│       ├── 2.png
│       └── ...
└── proofs/
    └── {user_id}/
        └── {activity_id}/
            └── proof.{ext}
```

---

## Version
- Document Version: 1.2
- Last Updated: January 3, 2026
- API Version: v1
