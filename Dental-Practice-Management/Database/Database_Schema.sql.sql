USE DentalPracticeDB;
GO

-- 1. Patients
CREATE TABLE dbo.Patients (
    PatientID INT IDENTITY(1,1) PRIMARY KEY,
    NationalCode NVARCHAR(20) NULL,
    FirstName NVARCHAR(100) NOT NULL,
    LastName NVARCHAR(100) NOT NULL,
    Gender NVARCHAR(20) NULL,
    DateOfBirth DATE NULL,
    MobileNumber NVARCHAR(20) NULL,
    PhoneNumber NVARCHAR(20) NULL,
    EmailAddress NVARCHAR(255) NULL,
    ResidentialAddress NVARCHAR(500) NULL,
    PatientNotes NVARCHAR(MAX) NULL,
    IsActive BIT NOT NULL DEFAULT 1,
    CreatedAt DATETIME2(0) NOT NULL DEFAULT SYSDATETIME(),
    LastModifiedAt DATETIME2(0) NULL
);
GO

-- 2. Dentists
CREATE TABLE dbo.Dentists (
    DentistID INT IDENTITY(1,1) PRIMARY KEY,
    DentalLicenseNumber NVARCHAR(50) NULL,
    FirstName NVARCHAR(100) NOT NULL,
    LastName NVARCHAR(100) NOT NULL,
    MobileNumber NVARCHAR(20) NULL,
    Specialization NVARCHAR(150) NULL,
    EmailAddress NVARCHAR(255) NULL,
    IsActive BIT NOT NULL DEFAULT 1,
    CreatedAt DATETIME2(0) NOT NULL DEFAULT SYSDATETIME()
);
GO

-- 3. Clinic Staff
CREATE TABLE dbo.ClinicStaff (
    ClinicStaffID INT IDENTITY(1,1) PRIMARY KEY,
    FirstName NVARCHAR(100) NOT NULL,
    LastName NVARCHAR(100) NOT NULL,
    JobTitle NVARCHAR(100) NULL,
    MobileNumber NVARCHAR(20) NULL,
    HireDate DATE NULL,
    IsActive BIT NOT NULL DEFAULT 1,
    CreatedAt DATETIME2(0) NOT NULL DEFAULT SYSDATETIME()
);
GO

-- 4. Appointment Statuses
CREATE TABLE dbo.AppointmentStatuses (
    AppointmentStatusID INT IDENTITY(1,1) PRIMARY KEY,
    StatusCode NVARCHAR(30) NOT NULL UNIQUE,
    StatusName NVARCHAR(100) NOT NULL
);
GO

-- 5. Appointments
CREATE TABLE dbo.Appointments (
    AppointmentID INT IDENTITY(1,1) PRIMARY KEY,
    PatientID INT NOT NULL,
    DentistID INT NOT NULL,
    AppointmentStatusID INT NOT NULL,
    AppointmentStartDateTime DATETIME2(0) NOT NULL,
    AppointmentEndDateTime DATETIME2(0) NOT NULL,
    AppointmentReason NVARCHAR(300) NULL,
    AppointmentNotes NVARCHAR(MAX) NULL,
    CancellationReason NVARCHAR(500) NULL,
    CreatedAt DATETIME2(0) NOT NULL DEFAULT SYSDATETIME(),
    LastModifiedAt DATETIME2(0) NULL,

    CONSTRAINT FK_Appointments_Patients
        FOREIGN KEY (PatientID) REFERENCES dbo.Patients(PatientID),

    CONSTRAINT FK_Appointments_Dentists
        FOREIGN KEY (DentistID) REFERENCES dbo.Dentists(DentistID),

    CONSTRAINT FK_Appointments_Statuses
        FOREIGN KEY (AppointmentStatusID)
        REFERENCES dbo.AppointmentStatuses(AppointmentStatusID),

    CONSTRAINT CK_Appointments_DateRange
        CHECK (AppointmentEndDateTime > AppointmentStartDateTime)
);
GO

-- 6. Dentist Working Hours
CREATE TABLE dbo.DentistWorkingHours (
    DentistWorkingHourID INT IDENTITY(1,1) PRIMARY KEY,
    DentistID INT NOT NULL,
    DayOfWeek TINYINT NOT NULL,
    WorkStartTime TIME(0) NOT NULL,
    WorkEndTime TIME(0) NOT NULL,
    IsActive BIT NOT NULL DEFAULT 1,

    CONSTRAINT FK_DentistWorkingHours_Dentists
        FOREIGN KEY (DentistID) REFERENCES dbo.Dentists(DentistID),

    CONSTRAINT CK_DentistWorkingHours_Day
        CHECK (DayOfWeek BETWEEN 1 AND 7),

    CONSTRAINT CK_DentistWorkingHours_Time
        CHECK (WorkEndTime > WorkStartTime)
);
GO

-- 7. Dentist Time Off
CREATE TABLE dbo.DentistTimeOff (
    DentistTimeOffID INT IDENTITY(1,1) PRIMARY KEY,
    DentistID INT NOT NULL,
    TimeOffStartDateTime DATETIME2(0) NOT NULL,
    TimeOffEndDateTime DATETIME2(0) NOT NULL,
    TimeOffReason NVARCHAR(300) NULL,

    CONSTRAINT FK_DentistTimeOff_Dentists
        FOREIGN KEY (DentistID) REFERENCES dbo.Dentists(DentistID),

    CONSTRAINT CK_DentistTimeOff_DateRange
        CHECK (TimeOffEndDateTime > TimeOffStartDateTime)
);
GO

-- 8. Treatment Categories
CREATE TABLE dbo.TreatmentCategories (
    TreatmentCategoryID INT IDENTITY(1,1) PRIMARY KEY,
    CategoryName NVARCHAR(150) NOT NULL,
    CategoryDescription NVARCHAR(500) NULL,
    IsActive BIT NOT NULL DEFAULT 1
);
GO

-- 9. Dental Treatments
CREATE TABLE dbo.DentalTreatments (
    DentalTreatmentID INT IDENTITY(1,1) PRIMARY KEY,
    TreatmentCategoryID INT NULL,
    DentalTreatmentName NVARCHAR(200) NOT NULL,
    StandardFee DECIMAL(19,4) NOT NULL DEFAULT 0,
    EstimatedDurationMinutes INT NULL,
    TreatmentDescription NVARCHAR(1000) NULL,
    IsActive BIT NOT NULL DEFAULT 1,

    CONSTRAINT FK_DentalTreatments_Categories
        FOREIGN KEY (TreatmentCategoryID)
        REFERENCES dbo.TreatmentCategories(TreatmentCategoryID),

    CONSTRAINT CK_DentalTreatments_Fee
        CHECK (StandardFee >= 0),

    CONSTRAINT CK_DentalTreatments_Duration
        CHECK (EstimatedDurationMinutes IS NULL
               OR EstimatedDurationMinutes > 0)
);
GO

-- 10. Clinical Visits
CREATE TABLE dbo.ClinicalVisits (
    ClinicalVisitID INT IDENTITY(1,1) PRIMARY KEY,
    AppointmentID INT NULL,
    PatientID INT NOT NULL,
    DentistID INT NOT NULL,
    VisitDateTime DATETIME2(0) NOT NULL DEFAULT SYSDATETIME(),
    Diagnosis NVARCHAR(MAX) NULL,
    ClinicalNotes NVARCHAR(MAX) NULL,
    FollowUpDate DATE NULL,
    CreatedAt DATETIME2(0) NOT NULL DEFAULT SYSDATETIME(),

    CONSTRAINT FK_ClinicalVisits_Appointments
        FOREIGN KEY (AppointmentID)
        REFERENCES dbo.Appointments(AppointmentID),

    CONSTRAINT FK_ClinicalVisits_Patients
        FOREIGN KEY (PatientID) REFERENCES dbo.Patients(PatientID),

    CONSTRAINT FK_ClinicalVisits_Dentists
        FOREIGN KEY (DentistID) REFERENCES dbo.Dentists(DentistID)
);
GO

CREATE UNIQUE INDEX UX_ClinicalVisits_Appointment
ON dbo.ClinicalVisits(AppointmentID)
WHERE AppointmentID IS NOT NULL;
GO

-- 11. Visit Treatments
CREATE TABLE dbo.VisitTreatments (
    VisitTreatmentID INT IDENTITY(1,1) PRIMARY KEY,
    ClinicalVisitID INT NOT NULL,
    DentalTreatmentID INT NOT NULL,
    Quantity INT NOT NULL DEFAULT 1,
    UnitFee DECIMAL(19,4) NOT NULL,
    DiscountAmount DECIMAL(19,4) NOT NULL DEFAULT 0,
    LineTotal AS
        (CONVERT(DECIMAL(19,4),
        (Quantity * UnitFee) - DiscountAmount)) PERSISTED,
    ToothCode NVARCHAR(10) NULL,
    TreatmentNotes NVARCHAR(1000) NULL,

    CONSTRAINT FK_VisitTreatments_Visits
        FOREIGN KEY (ClinicalVisitID)
        REFERENCES dbo.ClinicalVisits(ClinicalVisitID),

    CONSTRAINT FK_VisitTreatments_Treatments
        FOREIGN KEY (DentalTreatmentID)
        REFERENCES dbo.DentalTreatments(DentalTreatmentID),

    CONSTRAINT CK_VisitTreatments_Quantity
        CHECK (Quantity > 0),

    CONSTRAINT CK_VisitTreatments_Amounts
        CHECK (UnitFee >= 0 AND DiscountAmount >= 0
               AND DiscountAmount <= Quantity * UnitFee)
);
GO

-- 12. Patient Allergies
CREATE TABLE dbo.PatientAllergies (
    PatientAllergyID INT IDENTITY(1,1) PRIMARY KEY,
    PatientID INT NOT NULL,
    AllergenName NVARCHAR(200) NOT NULL,
    AllergicReaction NVARCHAR(500) NULL,
    SeverityLevel NVARCHAR(50) NULL,
    AllergyNotes NVARCHAR(1000) NULL,

    CONSTRAINT FK_PatientAllergies_Patients
        FOREIGN KEY (PatientID) REFERENCES dbo.Patients(PatientID)
);
GO

-- 13. Patient Medical Notes
CREATE TABLE dbo.PatientMedicalNotes (
    PatientMedicalNoteID INT IDENTITY(1,1) PRIMARY KEY,
    PatientID INT NOT NULL,
    MedicalNoteType NVARCHAR(100) NULL,
    MedicalNoteText NVARCHAR(MAX) NOT NULL,
    CreatedAt DATETIME2(0) NOT NULL DEFAULT SYSDATETIME(),

    CONSTRAINT FK_PatientMedicalNotes_Patients
        FOREIGN KEY (PatientID) REFERENCES dbo.Patients(PatientID)
);
GO

-- Supporting indexes
CREATE INDEX IX_Appointments_Patient_Date
ON dbo.Appointments(PatientID, AppointmentStartDateTime);
GO

CREATE INDEX IX_Appointments_Dentist_Date
ON dbo.Appointments(DentistID, AppointmentStartDateTime);
GO

CREATE INDEX IX_ClinicalVisits_Patient_Date
ON dbo.ClinicalVisits(PatientID, VisitDateTime);
GO

PRINT N'DentalPracticeDB tables created successfully.';
GO