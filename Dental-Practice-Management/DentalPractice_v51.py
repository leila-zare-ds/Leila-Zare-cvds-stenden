import tkinter as tk
import math
import json
from tkinter import ttk, messagebox
import pyodbc

from pathlib import Path

# Read SQL Server settings from db_config.txt beside this Python file.
CONFIG_FILE = Path(__file__).resolve().parent / "db_config.txt"


def load_db_config():
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"Database configuration file was not found: {CONFIG_FILE}\\n"
            "Create db_config.txt in the same folder as the application."
        )

    settings = {}
    for line in CONFIG_FILE.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        settings[key.strip().upper()] = value.strip()

    server = settings.get("SERVER", "")
    database = settings.get("DATABASE", "DentalPracticeDB")
    driver = settings.get("DRIVER", "ODBC Driver 17 for SQL Server")
    if not server:
        raise ValueError("SERVER is missing in db_config.txt")

    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )


def get_connection():
    return pyodbc.connect(load_db_config(), timeout=10)



def save_patient():
    first_name = entry_first_name.get().strip()
    last_name = entry_last_name.get().strip()
    national_code = entry_national_code.get().strip()
    mobile = entry_mobile.get().strip()

    if not first_name or not last_name:
        messagebox.showwarning("Validation", "First name and last name are required.")
        return

    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute("""
                INSERT INTO dbo.Patients
                    (FirstName, LastName, NationalCode, MobileNumber)
                VALUES (?, ?, ?, ?)
            """, first_name, last_name, national_code or None, mobile or None)

        messagebox.showinfo("Success", "Patient saved successfully!")
        entry_first_name.delete(0, tk.END)
        entry_last_name.delete(0, tk.END)
        entry_national_code.delete(0, tk.END)
        entry_mobile.delete(0, tk.END)

    except pyodbc.Error as error:
        messagebox.showerror("Database Error", str(error))



def show_patient_file(patient_id):
    """Open the complete multi-tab patient chart. Secondary tabs are UI forms only
    until their SQL table schemas are confirmed."""
    window = tk.Toplevel(root)
    window.title(f"Patient File v50 - ID {patient_id}")
    window.geometry("1180x800")
    window.minsize(950, 650)
    # Always open the patient file maximized on Windows.
    try:
        window.state("zoomed")
    except tk.TclError:
        window.attributes("-fullscreen", True)

    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute("""
                SELECT PatientID, FirstName, LastName, NationalCode, MobileNumber
                FROM dbo.Patients WHERE PatientID = ?
            """, patient_id)
            patient = cursor.fetchone()
        if patient is None:
            messagebox.showerror("Patient Not Found", "The selected patient could not be found.", parent=window)
            window.destroy()
            return
    except pyodbc.Error as error:
        messagebox.showerror("Database Error", str(error), parent=window)
        window.destroy()
        return

    patient_name = f"{patient.FirstName or ''} {patient.LastName or ''}".strip()
    header = tk.Frame(window, bg="#243447", padx=18, pady=13)
    header.pack(fill="x")
    tk.Label(header, text="PATIENT FILE", bg="#243447", fg="white", font=("Arial", 16, "bold")).pack(anchor="w")
    header_patient_label = tk.Label(header, text=f"{patient_name}    |    Patient ID: {patient.PatientID}",
             bg="#243447", fg="white", font=("Arial", 11))
    header_patient_label.pack(anchor="w", pady=(5, 0))

    # Use explicit navigation buttons instead of ttk.Notebook tabs.
    # This avoids platform/theme issues where only the first tabs are rendered.
    navigation = tk.Frame(window, bg="#e8edf2", padx=8, pady=6)
    navigation.pack(fill="x", padx=12, pady=(10, 0))
    page_container = ttk.Frame(window)
    page_container.pack(fill="both", expand=True, padx=12, pady=(8, 8))
    pages = {}
    navigation_buttons = {}
    active_page = {"name": "Patient Information"}
    expected_tabs = [
        "Patient Information", "Medical Screening", "Medical History",
        "Dental Chart", "Clinical Visits", "Appointments", "Images & Documents"
    ]

    def show_page(title):
        if title not in pages:
            return
        # Always pull the patient's latest identity from SQL Server before showing a section.
        # This keeps Patient File synchronized with edits made in Patient Management.
        try:
            refresh_patient_information(show_message=False)
        except NameError:
            pass
        pages[title].tkraise()
        active_page["name"] = title
        for name, button in navigation_buttons.items():
            button.configure(relief=("sunken" if name == title else "raised"),
                             bg=("#1f5f91" if name == title else "#34495e"),
                             fg="white")

    def tab(title):
        frame = ttk.Frame(page_container, padding=16)
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        pages[title] = frame
        button = tk.Button(
            navigation, text=title, command=lambda name=title: show_page(name),
            font=("Arial", 9, "bold"), bg="#34495e", fg="white",
            activebackground="#1f5f91", activeforeground="white",
            relief="raised", bd=1, padx=9, pady=8, cursor="hand2"
        )
        button.grid(row=len(navigation_buttons) // 4,
                    column=len(navigation_buttons) % 4,
                    padx=3, pady=3, sticky="ew")
        navigation_buttons[title] = button
        for nav_col in range(4):
            navigation.grid_columnconfigure(nav_col, weight=1, uniform="nav")
        return frame

    def add_entry(parent, label, row, col=0, width=25):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=6, pady=6)
        ent = ttk.Entry(parent, width=width)
        ent.grid(row=row, column=col+1, sticky="ew", padx=6, pady=6)
        return ent

    def add_combo(parent, label, row, values, col=0, width=22):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=6, pady=6)
        cb = ttk.Combobox(parent, values=values, width=width, state="readonly")
        cb.grid(row=row, column=col+1, sticky="ew", padx=6, pady=6)
        return cb

    def add_text(parent, label, row, col=0, width=65, height=3):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="nw", padx=6, pady=6)
        box = tk.Text(parent, width=width, height=height, wrap="word")
        box.grid(row=row, column=col+1, sticky="ew", padx=6, pady=6)
        return box

    def add_record_table(parent, columns, headings):
        holder = ttk.Frame(parent)
        holder.pack(fill="both", expand=True, pady=(12, 4))
        tree = ttk.Treeview(holder, columns=columns, show="headings", height=9)
        for key, heading in zip(columns, headings):
            tree.heading(key, text=heading)
            tree.column(key, width=135, anchor="center")
        yscroll = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=yscroll.set)
        tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")
        return tree

    # 1. Patient Information
    f = tab("Patient Information")
    ttk.Label(f, text="Patient Details", font=("Arial", 14, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 14))
    info = [("Patient ID", patient.PatientID), ("First Name", patient.FirstName),
            ("Last Name", patient.LastName), ("National Code", patient.NationalCode),
            ("Mobile Number", patient.MobileNumber)]
    patient_info_entries = {}
    for i, (label, value) in enumerate(info, start=1):
        ttk.Label(f, text=label, width=20).grid(row=i, column=0, sticky="w", padx=6, pady=9)
        ent = ttk.Entry(f, width=38)
        ent.grid(row=i, column=1, sticky="w", padx=6, pady=9)
        ent.insert(0, "" if value is None else str(value))
        patient_info_entries[label] = ent
        if label == "Patient ID":
            ent.configure(state="readonly")
    ttk.Label(f, text="The fields above are loaded from dbo.Patients.", foreground="#526579").grid(row=7, column=0, columnspan=3, sticky="w", pady=15)

    def refresh_patient_information(show_message=True):
        """Reload the patient's current values directly from SQL Server."""
        try:
            with get_connection() as connection:
                cur = connection.cursor()
                cur.execute("""
                    SELECT PatientID, FirstName, LastName, NationalCode, MobileNumber
                    FROM dbo.Patients WHERE PatientID = ?
                """, patient_id)
                latest = cur.fetchone()
            if latest is None:
                messagebox.showerror("Patient Not Found", "This patient no longer exists.", parent=window)
                return False
            values = {
                "Patient ID": latest.PatientID,
                "First Name": latest.FirstName,
                "Last Name": latest.LastName,
                "National Code": latest.NationalCode,
                "Mobile Number": latest.MobileNumber,
            }
            for field, value in values.items():
                entry = patient_info_entries[field]
                old_state = str(entry.cget("state"))
                if old_state == "readonly":
                    entry.configure(state="normal")
                entry.delete(0, tk.END)
                entry.insert(0, "" if value is None else str(value))
                if old_state == "readonly":
                    entry.configure(state="readonly")
            latest_name = f"{latest.FirstName or ''} {latest.LastName or ''}".strip()
            header_patient_label.configure(text=f"{latest_name}    |    Patient ID: {latest.PatientID}")
            if show_message:
                messagebox.showinfo("Refreshed", "Patient information was reloaded from the database.", parent=window)
            return True
        except Exception as error:
            messagebox.showerror("Refresh Error", str(error), parent=window)
            return False

    # Force an immediate database read after the Patient Information widgets exist.
    # This overwrites any stale values carried by the selected row/object.
    refresh_patient_information(show_message=False)

    # Automatically refresh patient identity when this window regains focus.
    # This is important when Patient Management was used to edit the same patient.
    window.bind(
        "<FocusIn>",
        lambda event: refresh_patient_information(show_message=False)
        if event.widget is window else None
    )

    # 2. Medical Screening
    f = tab("Medical Screening")
    ttk.Label(f, text="Medical Screening", font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 12))
    grid = ttk.Frame(f); grid.pack(fill="x")
    bp = add_entry(grid, "Blood Pressure", 0)
    pulse = add_entry(grid, "Pulse (bpm)", 0, 2)
    diabetes = add_combo(grid, "Diabetes", 1, ["No", "Yes", "Unknown"])
    heart = add_combo(grid, "Heart Disease", 1, ["No", "Yes", "Unknown"], 2)
    blood = add_combo(grid, "Bleeding Disorder", 2, ["No", "Yes", "Unknown"])
    pregnancy = add_combo(grid, "Pregnancy", 2, ["Not applicable", "No", "Yes", "Unknown"], 2)
    medication = add_entry(grid, "Current Medication", 3, width=55)
    allergies = add_entry(grid, "Known Allergies", 4, width=55)
    screening_notes_frame = ttk.Frame(f)
    screening_notes_frame.pack(fill="x", pady=(10, 0))
    screening_notes = add_text(screening_notes_frame, "Additional Screening Notes", 0)

    # 3. Medical History
    f = tab("Medical History")
    ttk.Label(f, text="Medical Conditions, Allergies & Medication History", font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 10))
    grid = ttk.Frame(f); grid.pack(fill="x")
    h_type = add_combo(grid, "Record Type", 0, ["Medical Condition", "Allergy", "Medication", "Surgery", "Other"])
    h_name = add_entry(grid, "Name / Description", 0, 2, 30)
    h_date = add_entry(grid, "Date / Since", 1)
    h_status = add_combo(grid, "Status", 1, ["Active", "Resolved", "Historical"], 2)
    h_reaction = add_entry(grid, "Reaction / Details", 2, width=55)
    h_notes = add_entry(grid, "Notes", 3, width=55)
    history_tree = add_record_table(f, ("type", "name", "date", "status", "details", "notes"),
                                    ("Type", "Name", "Date", "Status", "Reaction / Details", "Notes"))
    def add_history():
        kind = h_type.get().strip()
        name = h_name.get().strip()
        if not name:
            messagebox.showwarning("Required", "Enter a name or description.", parent=window); return
        try:
            with get_connection() as connection:
                cur = connection.cursor()
                if kind.lower() == "allergy":
                    cur.execute("""
                        INSERT INTO dbo.PatientAllergies
                        (PatientID, AllergenName, AllergicReaction, SeverityLevel, AllergyNotes, CreatedAt)
                        VALUES (?, ?, ?, NULL, ?, SYSDATETIME())
                    """, patient.PatientID, name, h_reaction.get().strip() or None,
                         (f"Status: {h_status.get().strip()} | Date/Since: {h_date.get().strip()} | " if (h_status.get().strip() or h_date.get().strip()) else "") +
                         h_notes.get().strip())
                else:
                    details = f"{name}\nDate/Since: {h_date.get().strip()}\nStatus: {h_status.get().strip()}\nReaction/Details: {h_reaction.get().strip()}\nNotes: {h_notes.get().strip()}"
                    cur.execute("""
                        INSERT INTO dbo.PatientMedicalNotes (PatientID, MedicalNoteType, MedicalNoteText, CreatedAt)
                        VALUES (?, ?, ?, SYSDATETIME())
                    """, patient.PatientID, kind, details)
            history_tree.insert("", "end", values=(kind, name, h_date.get(), h_status.get(), h_reaction.get(), h_notes.get()))
            for w in (h_name, h_date, h_reaction, h_notes): w.delete(0, tk.END)
            messagebox.showinfo("Saved", "Medical history record saved to SQL Server.", parent=window)
        except Exception as error:
            messagebox.showerror("Database Error", str(error), parent=window)

    ttk.Button(f, text="Add History Record", command=add_history).pack(anchor="e", pady=6)

    # 4. Dental Chart
    f = tab("Dental Chart")
    ttk.Label(f, text="Dental Chart / Tooth Condition", font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(f, text="Select a tooth from the diagram. The selected tooth number will fill the form below.",
              foreground="#526579").pack(anchor="w", pady=(0, 8))

    # Anatomical horseshoe dental arches with clickable FDI markers.
    # Background illustration is embedded in this file (no external image dependency).
    _chart_png_data = "iVBORw0KGgoAAAANSUhEUgAABEwAAAHWCAIAAADipotvAABNSElEQVR4nO3de5SWV2Hv8T0zkAtILhKd5CWByUAuaiBe0jTWqlEDuIyXnkrVpEdTj6JobBvbo0vX6bE97VnLU+2qLFssFrsMug544dTWeGOIGrWNaUyjQrwkhsmQhIkkYC6EgAwD548Nm81z2c9+nmc/+9nPfr+flZU1vLy8s5+Z9917/559G9h/cFoAAAAAQCwG2y4AAAAAALhEyAEAAAAQFUIOAAAAgKgQcgAAAABEhZADAAAAICozXL3Q+OQeVy8FAAAAoD+N9ubWf5GBmltIk20AAAAAOFcn7VQMOels4yRyAQAAAOhnToJGlTU5+jce7c2V/1V4HQBAUNZu2tJ2EaroaLEBAJnS+aLC3LFyIzmJeFP2mwEAWrd205ZVK5ZmPq7/MfM5QbEpcN7FAgC6oloAKRFy1Dcg3gBAF+WlgvE164UQY8M9IcQN1ywXQqzeuFn+1bJdk16LaEcWVeSXdvT668SJ10vUAYBOK5tEbEMOCQcA0kIYKJARpZCeYUQqGCT+NvEcEUbaUdlGpIoqTryixDMrXIiMSa0I4U0FAAEqlUesQo58ReINAOjMS0Es+6mWEaWOzAAj6b3/wue0m3MSozeZCi/H57WUiknp9xI5BwAyWQaT4pBDwgGATLJj2m5P2swmGIhjBbYJD21dkeWFCCFWb9wsh27yntn6tSj6cJPIGWRLJCUGeQBA2MWTgpDDLDUA/UwtVkl3iM3d7hB60vbBwEaLV+T2QsSxawl5YCrzp63+SWLpEQD0G5uEYhVySDgAomQzVSxxu131Lw1zwKTWc05hCctq64qiuRCl1NS7xBIjxabwpCAAsSoMKaaQQ8IB0HU1V7zk7eKl2EwDk1oJBsIiG2zdfkLBlizM6E8r6oqunTOzRulK2LB3Sn7R0IWEPDCVt8TIVeGJQAA6zRxVckMOE9UA+Fd2yUFzq/ZtNvKyHFtouj991qIF6QdlNjCXMJEKdIaE4DPnWCacOheSdxW7791hVcQyKsy7y1ti5Cc/10xBrCAC0ChzWikIOSQcAE0oPKI+cYSLZw0tAhFZ/dHMiFJTqYSTiAF5j+v85JyyCafshTR9FYmY5PxNJdqed6cikOHjTMgB0ChDYGk25Lz1/R9eOH+eGBDT04ff/DvLRuf3hBDfvu2HN276+sf//I9PnzP7jm0//8Z3bhdC3H3f/RedP18IsezFv7Huczet+/D7j/9zIYQQz7/kwlddecUfvO/Di0bm/dn1b5EPrvzgR9Z9+P3pF9n+wOSn//oDEw8+9LmvfOvQ9PTQ4OA7rnnt3DNO00t1RBw5cODgf/0vy561cIF8HSHEt75/57dv++HQ4OCsU095+xuufvoZp6nvoi4q75sue/FvXH7ps+r8uID+kbcvmWi73ya6P9HLJhuYA4B9zvEQcqolHJu/FYH9UqRSbyrR9iYKNtsnkHMQqzB7uYlea+Y3SjzyzLlndLdPawgsM8r+g1JmDA392XveIoR44KGH/3Hjl//qT94uhLjzJ/csf8nlP/rZL156+XMvW3zxZYsvFkKs/OBH5DOFEOs+d1PinyszZwwdPnz4Z/fueJZ27zP9Iis/+BEhxCc33vS+lW96+hmn3f7jn2341y1/eN3r06Va89kv/Z/3v1M+vu3u8Tu2/vwv/uitQ0ODN33z1n/83E0fWPX7eZeWWXIAeZIDMlkLqSV1dKPsP7XVe6swP0o+mNcrTRxJ2TSb4YK8oi5Z2DNMAAtQ5QsJ6pdS4U0ljl1C5gaAjbK5FyDLlh6MZS0Q4hBmL9dQTsMj3e3Tjvbmjk/uGZ/ck44t2SHHufPOeebDv3pMCHHw4NSvD0697Irnff6r33rp5c+t8FKvf+WVm75xy/98j6mKPPuZc4UQTzy5b+rQISHECy656PQ5s9NPO/fsZz76+F71x69++/tveNXLhoYGhRBLf/uyX0w8ePjwkcHBgQqFBPqceY5Z4WZZ+ir/pqNOYrZY/YleW7dPmnPOhr1TzY0bqBEDg8J+szgWD9q9lkJOLkRq90JEjTeVkp732MSyIlF+3l06gK3dtCXxCLEHnRZmLxeeQs5P7rlvwbyzhRBb795+6cULz3nm3Ed+9fih6ekZQ0NlX+o5F4z88+bv/PTeiWcvGsl7zl+9921CiDde/fK//Pj6S5+96LcvW5z55G13b3/2Bccff/CXj5zXG5Zfn3LySX/ytjeULRvQhwrzTOV8kog6lV+n7KKXyvOj1LiBTZe0UQ5XfUTPw2BOYXKu+abKC5zmd36FCFRhWVHix6teIfGJzqxGSD7oijB7ucgIOQ63HDg0Pf2///4zR8SRWaecsvKNrxZC3LHtnh07f3n7j3/22ON7f3bvjsUXjRb+c/n1G1/98gtGzpVfr3jllV/8+i0f+sMR83d/yeWXvuCSi+646+ef/dLYZYsvev0rX6q/7PTh6clde/76A6vU8w8fPiy/+Nott9151z2P7X3ybz747kQx5B/L/AyAqJTaBkB2aDKP+LBXOHvN4cJ9m2EQqbsTvcoWr/XAlieaC1E8v6kKPzh5KahChM7cir3wzgXz3BC4MHu5Nt9If+Rtb7j6nGd2e5uxvBlrzY7kJOb8HT585JeP7Pnw+94hhNj68+0//OkvzL/+9JRB6VmLFgwODvzkFxOGf/vEk0/98pFfXXj+uS+9/LnPe/aFH/jIWvXrVy/7lW/d+t3bf/zaV7xIPn72M57+wOSu0fm9V115xZW/+dx3f+hjmcWQUyGB6Lk9YUaX3g/XTO8YNbEXWfp75ak/P6rpWV7Xzpm5Ye9U4U/YprsffmATUVxIsLMHK8zkNJRN/4eV190x4IOghNnLtflGed86Mp6mq0n33PfA/GPzwS4enf/ZL41VfqkVr7zyC1/7luEJAwPi4+s3/a8b/tvcM0578qmn5p55evo5l1w0+qXN31N/fPkLn7/p67f86dvfNDQ0OPZvd7AaB32loZ2aM7tE+oP2e0k1HQ/sh3E6rdRoRshDH9FcSEzyPs7pesDVZFTBgA+CEVovF15Dzn/edfdzjq2BOemkmafNmbVz1+55w2flPV8fTbtg5Nw3vvrl6q8uXjh/xtDQ1KHcmWNzZs96+xtf/fEbN82cOWNwcPCdb3pN+jm9Z8x94KFdR44ckX980QuW7Ny1+wMf+eSZpz/tRZctHhocLH+JQBDMZ/B5OHmmcGsBEeQGZZVPnMx7ftx96xD2Hug6h2+qdn8ddbaGE7VzToL9gA/HlcKhQHq5h6an/9fHb5RfX3j+ede85hWGbxS3jHNyOAYU6KLM8/hWrVjq/zBNm9XJNQ9wdN6Ns99UzTK3mJ/c6CEzlacVVRDHhbR4FQ7fVKLJC7G5inTZbA5cEm0c9WOzUJDwA3RIZnjxOpIDwK1EsMlc/SKaP21Gn7tf8yTKwr2kPB9somN+VJ7ZI/Maed1tE428bEgieFPV329QHfWjx7Mm9r/Ws405PLdVyQBwiJADdNX4mvXC+sAZh6fN2Cz9b/okSudzcizX6wfrhJjhKxvIjuDKxSN+vl3T9J/hvomdLZYkNDZDas63hnN47I99ttGpw3xY4QN0FCEH6IzKE89Uu65uT1qmnSa2MnO1QZnzgnmTnlPkdiRk5eKRddsmuhvYlBYvpP5vxH9ManTSXR6H57EWyqyOLJNP2beQXskkKl4yD9AVhBwgaIZgY7O4P8G8zLd+pPG5GqTr692dT/Hy3KtWXequD3qovqy6ECe/GvUiK4WII3M2qvKdi8IBnzrndGXWk3qdTOABQkbIAcLS9D4BqjPR9IEzmULeoKzdGWtNRIUIOtbefil6YK7/u2hqkVIbDHcunH+cndy5SNZse6eqvXkyc1ci9jDIA4SMkAO0zDLV1LkfmdD6zr+hHeB4vEvqazVL0wMgMhs09/qtzIxqQkMXkvjl+szP6s3sbYQttI+zrv6nIF3xGna7JvMAQSHkAL5VGKvJSzjpPpP92ZqijRlfbe0lZXln3cMiEG+ribq+lYLS3IV0emVXIfN73kkE6sTWcKUOv0oUUt4P0l+h1Kk+ZB6gXYQcoHGuZqA5PFtTzcRwmHN8LshJ6OIycW+cx4M4hnFUwun6hUiJJVKFn4jCJ/j/RDgfYTYP41hWmInPTp1dT8g8gGeEHMA9t+tqbCaqmQ/jy5wK3/U9ykrtXBxxhjFQk9a6Pp7T3GCOt4TjeWCt8A1vn4I6vXFCtdNLLU/1qbkjP5kHaBohB3CjoQ0DVMJp4mzN1hfnVJOZzVzFmEY7o/7HQJwvzolpGKfrV6FUuFth/rxEsHGC4W1f//RSqX7O0Zk3bVu7acuqFUtdfS+gTxBygBL0lqa5bdDU7kCqne7E2ZpNL3ZPaHpwpqO3rtPiWJzj8CraGsBs6BfRxLy7VkY+nSfP5k4v1ffiVwWufFZpmmxcEmP4azdtUV8TeAAbhBygmN66HP96uCesT9U0M+/mbLMUp/JhfM4nrXW9My0imuWVENnl1BTHME5kK4tcKRzGqX96abrmTFTjFTJPItXkfVpXb9xM4AFsEHIAE9WWZLY3cma2/ohl5rE5o8bnqIgTs0fmyen7bRfEgchyjudBNvjhLeF4GAyU1yIX2sWxgq5s5rGZmZx4QqcXVQIeEHKADPp9MkOTY7+1aOWTNyvsqGZ+vquNXA2z9iMLBnFcTgScdLWjWY0T8RhOum5xFXtarDAtM0+p97YcTWK5DpCHkAOc4OhKm+GeqNTeiGM5p3KqqaDpw/jsVyHvm9gZ06BBTDknjpU5kGJNOPsmdmbWNpkPVk4+IZxemmggataZaoEoW7QBOkIOIISjXQROWI1a/+UsNHEYX6lIk/dX0XSmY8o59UUzDNJp8SUc/X2VrlXyaqQKAz5hnl5aaoMZM9IOoCPkoK853yFNtlJyX2bRqV6Iw/PRmx7M8bzztcOc03TJC+b9Wxy45OC7NKr5S/A5BltHh+qWmjIrn4IBnw6uDHR7D4W0AwhCDvpTnWyTmMOQebdPDel07ggayckM+JiGPvyM5zQdHpbtmhwb7sX0eylLfirNu4PU/y10JSaV1dDbptrwoP2AT+DM94MKm5vMk0n1P5J20M8IOegX9QdtMqdo521I2rmc43ZHo/hWgLgdnmpzMCSfmgfVxd9aOIU3/XJrj0S1MmOwoYFZt5uDdXFPNsNEtVLNjUhtP53eAsd82CgQJUIOImeTbcayeh6JVifvkGzD8djOj6DpIvkTaL3fWd/ue3fIHmqnk1vXB3O6Xn4o8a0sqsyQcGyaG9nQpLf6NGB4B32CkIM4VRi3MXSb8pocoW3C43Cz0TjIvkuHVu0Xjq7IHrbNS3XiehPUVK68FBFyYi8sfOAsy6wuc/cu09MCny+nv5H6OeHkjY9VaG4Sb57MOWyZSDuIGyEH8ag2IW3MerfovAxj2Gy0/kJzDz22RlfD66tZRKtDOg5niBl+KaoD18WutmTOcpbH3Tatwo/XZkFOK2TBHH5ACt/qLaYgBnAS8n7jFZqbOpjMhigRctB5zndISzBMg1Zkw+N2MCeaA2eaGNLJDGYeFrqoAFDtQpruZ9v0TlYJsXbTlrzyH32F1BNkyeufOXjzbVuFEFddsaTyK6w6dlavKuEJZdOO8dWpvnXhj6jp+iQE5k9KQxEosgEceTkrF4+4XQvkqrmxH8xJY3gH0SDkoKvq90XOWrRA9rzDueOe3CBo24To8piArqEhHf8r+JubtOa5S5Eunsowq1YsXaulhdAmqiWKl/6rvCUKNiGt/m/BUDWlJ9TZ/2y9jURlfKaGezU/sD4HcDzX6olK2zLzeCvkWYsWVK4kC9PO2k1b6t/4AJpDyEG48voxR1W6R1X2JmXZiQFlB3PM256uXDyyzkvO8XPyTOdW6ZilL0EfUkiMNgh3gyH1qZCQGAxJkH9bKiF4o8KM+mPeM/2XvyAmZVVr6j0T4OfCMtLbiGAARzLscVct80hum5vjtbrW6pUNPEd/+/ltsaxJgqocAIWQgxAVxJtj7MfiM7ON/b00m9xiOVW68DCHRKMYzaQ1pdSZM0H1+VTndZXFW9Qw2hACPeeYn6D+6KlktemDOQEmtHTxbMqmPzOcCXWl9kuIUqK6TlfvFTKPw+YmTTWFNmlH5Vvzb3n1xs0M6SBMhBwER3atLNtOWQvnRZ36k8tLDcsYDgbdsHdq5eKRzH9leauv64M5epu6zOL2sHkFf0NTd8pOVbLPaeEM4yj6iFOeAIutqBiWV7wAE46u7EQ1xfwu9RaByu6XoG8KF/j+b2aGYZwSmWfbRPqf129u7BWmHcuEo54Qcl2BvkXIQUDs442k+o76kE74zWfZhaqlhj5CYD8jwv5OsJMLd7joJT3jy/wcV9/XOUNUCHwwStiVMMBel15sc/Eq5DQ/OytUTmhSZhXhpOoOapllYeYJwVlZk9nsE44im2NmryEohBwEQTX5ZRsndQ9JVsohz/muswlPyJPWqq1qtdymrOxuZj7X7uvrKETOW9e+O9sic1QItthSZvEKB3k6oaGRqLIDQYbNEgo34dCfWViwdE0S4B0rwzBOIdUEBJXEdGozHqlCcyx/PuNr1rMzG0JAyEHLjrap1ofVZFJ1a9NL5+twUrZGB3MKZ6y53cqsQs4R2u86kP5rYrgmkFKVlVfsjl6OFHLh5dsmwIl22X3TrK327CeLVp5W2tyATzUhD8k6oRJO/VZGtuxEHbSLkIN2OJ84roZ0ZDUdVNTRF0BX5n/Sms9jZ/LINnKVEELbr6zpUpVlXtxi7s6iIeH/wPPmBwa4lChRMKGXLX8MsKGPaisDPl08w7TsoJOThJNo7DhyB+0i5MC3avEmsZNM3ppLJ3GiOTUHc9S/VdfYUNrxdvjM6PXXiaKVLUrgS0TMh7d4Lgw6LfA3TKni+TzYZ6zejIC05rJNaHPVChOOZRMspTc+ZWAHrSDkwJPKQzeZG2UajoX2c+RLWW7TlzpwpvLBmq3sYZDZwtms4E8/OcxeYJilQreE+S4q+9FT1V36U+9/C+yy1Z1eVztvR4JdXSlympKyTbABAzvwjJCDxtVp0lT1mqhM5eNlT94MgcP0lR7YERaBx7w1syul2rBqOQeIT5gJRymbcDKfn1k5NJd8ym517WFmWpjDOOaE47YJZmAHfhBy0BSbRktfj5GuYfOqV6EdhdahnNPc7ghqYEdYRxe1Y5Jw0eLWb6sSO5XZPBmAT/aHllo+WdfEgE+FwfOmE07Iwzhp1Zpg2dIlFltmzlpkYAdNI+TAvcLGyZxtEvIyjOHI5zBnrInGlgzJKenqhM1SOUd/vs0Jm422RqpjxFgN0CFNbJZQc8AnsQtc4enDiX+ye1dT+xn4GcZR1zJ7ZF6d0wtE1SY4XRIDBnbQkIH9B6cTD41P7hFCjPbmtlEedJh982OzPNRyym/e0wwby6gT2dYdO3Pa5+QBV3cK6xxTnQgzhltu7bY6bEoWn5tv2yqEuOqKJW0XBG60fgxUot3Jq80KGx3z1tidO6hUXs7KxSP6g3lpZ8PeqbyZFJWb4HRh7LegIO2ggszwwkgOHKgwr8D/pOT0adMrF4/InONzFX7lwRzLHc/Sp8rY/xMpnAaGhAOEr93PabK+0gaBK2zslvdPEtVv5czjM+FcO2fmvomdesOnvtbTToAz6BjYgSuEHFRXbc60zbSBb37xaw//xw8GhobGZwxe8qqrFr3ociHEwaee+v5nvjjxgx9e90+rE8/Pmxa8Ye9U4laWpKp4/4fPKIWz6Srv46xPzzBcl96E6AfRAIClMO9EZJTKWLmVvfFUIfN4yxKJa1GNnZ52dj3x2D13/GhoaOjw9OEZvfMOzTtPCHHPLbfe851bDx448JvX/O6e2WeU+qY2i2PPWrSgVKPGih3UR8hBFXq8Se+In+doS1BU1z+49aeP/OcPL37rm5/3nNGDTz21+SNrnjb3zLMvvmDso584/4oX7LjjR/qTDdOC0zIH6/WcI7zcacsbzHF7Ok16yU0hNi4D0HXphCOrtbxq0DxRzYZl5vHQuBimQ6vm74nDh8Z/dNfLr11x0iknHzzw6y/c+Pkjp5x64Im993z3+1d/6E8ff2jXzX+79sJ3vUPY7RBdqgmWPxnLlk51LRjYQWWEHJQg65qx4Z44cTRGdqbzWoiyI/tbvzL28rdd88wLRoUQJ82adfm1v/ujf/n62Rdf8Io/fsepZ5z2n1/8cuL55op43baJwtUvFXYnc6K5Mzdle7DqWOteKuc0VCQAaFrZGqx+wklLZx7PU8LMTd5dt/z7s5ZcMvXL3VNCbNg7NfSsSy7ct+fAk/ues/zKgYGBp80988CT+0rtWVr45MRWQKpLYGgBZafihHkfJ96Ao6mCDUIOCpxwaz9/7abaMlJvKqrd0Hps50NzR847/iLnz3/0wUkhxKlnnFaq5GW3bG5x6lp9eXe59CNo5CM3XLNc/mRY1g+gnxk2hXN4bs/ue3cIi0na9Rm229E9+fgTp595hvrj9BmnP3r3tjN6Z5/RO1sIcd9/3Dn/+YubLOZxmQM7lnvnhHwqNMJByIGJSjiFnX61B/HYcM9QyVa4oXXkiJg68Ouy/0qVqtRka7c5p+mwZDl8rzcDlgfRAECsEnVg4YmlzR1UKtw1ExUq9qPNsdbCPrHrka1f2XL1n723fnns6QM7NglHaP0NbtXBjJCDXPYJR1Gj0qLGFslnntvbfd/9wxculH/cM3H/mfPOqfZSiv2ZOa6W6JQ9ZtuGqzM3JZbfAOgfrg4qdZV5VHkq55x0sLFp5uacftpjjz76jZNPl3+85vKLfrD9p0KIqQO//tbH1734HW8+5bQ5FQpT04a9U4apIpn0492IOshEyEEGvftbtvJV9U7lqHPpa5bfvuGfl7//PSfNOvXgU0/9YOOXLn1t9ZBQdtKa0Mq8Ye+U3opUaIfk5D19qlipf+7n5E0AiFtzp5RWyDz6QiCb7UYT/0pXoYW94NkX//SHWwdecMWRmTPf/boXj330E5e+drk4cuQ7/3Dj4quXPnPR+WVfsFDhPDo1xaNCI6tmXwsaNaRwGCiSKgzg5Fm9cXO6XrM5EO0X3/3+TzZ/e2Bw8LGdvxRCXPbG1z1n+cvkX33m7e99y6c+VqEk8ovK40uJiXY2P5y8MzdV7kovdWUDGcSNw0ARt8zMU/mIUsXVKdLSF366/aT7th8ZGDjlwH4hxGVvfN3MU06+9cbPP2N0gRBixiknL3/f9fW/i2IIOXXiTfpbEHL6GYeBoph9wknsGpm3v4r9+Inugpe88IKXvFB+fWDvk48+cPx7VUg4osYRnEqiWaowwUC9gl4SUg0ARMM8zlNtDzd95Gf3LiFqnEYqZK44b/6h8+bLJky2sOc8+8ILX/pblV+zekmEEFn9DcsOBmBGyMFx42vW20yKzdwUXz6YeSJnzVKdMudp5zz7wpovopQNXek9LtVRm9XW24xef506eZOEAwARO1rJH1sfX3Num3pQNUxl0046V7htYStItKH2HYw0TtRBAtPVcJSqfM0D6KoCSlQ3eY9njlPbzFhrgv2Iv80JNpY7XQrG0IFjmK4GSONr1ptbW/0WYeEQkGXaaaXxte8GlO1g6K+v/4jIOX0oM7wMtlQYBGR8zXrL20uGikY9krgNE9SBM+bC7L53h/rP5tWW7ZpU+wqwLzMAwJ5lwlENjZlN++X5TNKyKnQw8tj3ahA3Qk5fy6wIEhuCpeUNGRuGkkOuW0sFm7TMlTYAAFSTOUXNXmaj5mqJf1llZ3NU6GDkIeqANTn9q+yH32ZS7JKFva3bJ7dun9SflliZM3tk3koh1m2baPqszEzqJJ9qjYeij4arNTZ5OYcDywAANjLP86nWWU8v3WlrbsXskXlCiH0TO/OeULmDUWh8zXpmr/UtQk4/MlSXlucNV7Bh79TKxSOJB1vJOXUY6spVK5ZyvCYAoKz0DbLEfTHV9FRPO9YH8jiUuC4ZddZtmxBO+xjy3mXePt2CDQn6GCGn7+RVkeZ4YzkRVn9++l7Lum0TMufsm9gpB6/VaZuBRx3LypHhGgBAIXVHLHPcxqBm2vFJ3+ln38ROmXAy1e9g6F2IvCkVDOn0IUJOH6kWb3Q2Y8RyQDnxoJqxJm/hqOm5186ZKefmOh/ScZKdqBABAE2oeVOsVNop3OTA+X3G9F6mcq5ahdU4iecUJiLD2RUM6fQbtpDuC+ZK0P7Q5fryNnF2viYyXcel7/RkLsuh+gOawxbSQHPMtzJVI5iZAZpofJtu6M1lMK+8pa2PTGZ4YSQnfkENaqtbLIlDOd0O6WRuTWPe/Yz6DgDQaebhncyDd9ze5TQcRtfW9m6ZxoZ7y5i91gcIOTHTz/fMvKVxdMcVv/s7G3KOcLRKJ3O0OvETkDU7dRwAIDLptFNzQ1EboSUc2cNJbKWt5uePDffEsZVRrKeNFdPV4iTrtbGc3VRkZaf2lNywd8r/nRWbEe08NqU1nDNAsAHawnQ1oC3p4Z1SwziWZ8EFknBWb9ysSrL73h3mtceJSyPzdFFmeCHkxCaxi7HN5znvaR4Ybvzksa8uE7NyyTZA6wg5QOv0WR6i5H1Ds0ASjtAOIS1VgLKb3SEchJyY6dnGvipRn+cW58hmHoecSR90ttwRTr44tRUQCEIOEAjZbbC8XSi0O4ZqGkihFtfhVO7ekHM6KjO8DLZUGLikEs4N1ywv9XkOYf2fLINhitrue3fI//QHl+2alBXu6o2bC+8wcUYnAABlZU78zmyU07qYcPR/Qs8hAoScztMTTrslca6wGi2MOvH9TAAAqKlwGEe1qqqdTTO00SHspVb5W5NzosHuat1mmXASh2fZHLnVosL7QwnLdk2OXn/d2k1bDEM6azdtYegZAIBChp170lSTnZ7G1krCydugtVRHSO3RSueh01iT02E2CcdwNrD6hNffsrk+uRFK2XgjUtsJUB8BIWNNDtA6mwEK2ZJWOGfvrEUL5DBOiwkn8d1tOkLmV6NfET4OA41KqYST+BjLx7dunwxqSGfD3qll1k/O2yqNmggAAANzQ6nfKzSfLppp9707RM7xFU0zJ5wKHaHMM/fQIazJ6aQ6CUd/RD5HvkhXPsmj11/HZtAAADQhMwJ1qOW1STgi1RHKxAatXcdITietWrHUcj1c3i2KJQt7hg92Q+rMi+tK9QoAQJQqDOzoGp0bb3jxoDpC8ImQ022rN27O/EjLz615Npr8eMuxWjkmm/dqbhmGjMaGe+lljsQbAADCIdvlzKijTrHzOT0k83uV7Qg1VTi0h5DTVfaDOYGw2a1lTJvIS7YBACBYeQM7ea28bOKd304N4VhzhIk1OZ2XvoFRdvjVz8ocVfuM5S9JlDVjh+b+AgDQ5/RW25xwhNMooh+Rl3jZah2hxIsLFuR0HCGnw+RnL6++sBl7zXxOWzlH1pLEGwAAOsemEXebcNRrOu8IIQ6ck9NVlseAVtPo4G963hrBBugTnJMD9Al9DpvzYRw/U9Q4J6dDMsMLIad7Go03uuYqESoOoD8RcoB+47zT4n8RDp2W8BFyOs9bvEmwnMBWqlRUGUAfIuQAfaVavyVvcwK9N9JKR4geS7Aywwu7q3WP//1DLPckqFb76IcrAwCAyNh3CVRHwtDlYBc1WCLkwFYi6lw7Z6YQYve9O9LPHBvuGUaTGcMBACB69gdd5B0ycdaiBfKLDXun5BckHNgj5KAceWyoyIk3kqqk9LSjI94AABAxPeHInoB5Blrm3tOyp6GiDgkHpRByUJrMOWPDPcOxnnLDtFXaI0xLAwCgTyRa/LWbthhueiaOE02QwzgkHJRFyOmSVSuWymoikI96Zs7J2w+ahAMAQH9KZx79EdlzMEcdoCwOA0UVmSmLozwBAEChzPuemb0IecZOIPd20S2M5MCkcEc1NZhDvAEAADWNXn9dekgnrzfiJ/xYHqSB0BByUMCw8EYi3gAAAFfU7DU5jBMIZt13DoeBdozP80DNe54I4g2AkjgMFEApeQt1VP5pujvEMaCdkBleWJPTMT4/ZqriyLyVQsIBAACNyuxseE446ChCTlf5+eBl5hw2GAAAAH4keh3+Ew7DOB1FyOke9WFrJecQbwAAgGey++Et4SgknO4i5HRSuzkHAADAM58Jh6U4ESDkdJXnD56qUNTOBwAAAH60svESOo2Q03nePorkHAAA4F8rCYdhnK7jnJwOW7ViqfzYqw9k2Q//6o2bbf6JnqP4zAMAAG9q3lq17OoI4k10OCcnHnotkPd5rjzswwceQH2ckwOgskTaqdDVMaQdFuF0WmZ4IeREyHzPI/MDrB+2pe+ftnbTFj7wAFwh5ABwwtDVWbZrMnMn2Lx7wQzgRICQ04/sU8r4mvVsDw2gUYQcAG4l+jk2nZl0QCLedB0hBwDQJkIOgHAwXSUameGF3dUAAADQd0g4cSPkAAAAAIgKIQcAAABAVAg5AAAAAKJCyAEAAAAQFUIOAAAAgKgQcgAAAABEhZADAAAAICqEHAAAAABRIeQAAAAAiAohBwAAAEBUCDkAAAAAokLIAQAAABAVQg4AAACAqBByAAAAAESFkAMAAAAgKoQcAAAAAFEh5AAAAACICiEHAAAAQFQIOQAAAACiQsgBAAAAEBVCDgAAAICoEHIAAAAARIWQAwAAACAqhBwAAAAAUSHkAAAAAIgKIQcAAABAVAg5AAAAAKJCyAEAAAAQFUIOAAAAgKgQcgAAAABEhZADAAAAICqEHAAAAABRIeQAAAAAiAohBwAAAEBUCDkAAAAAokLIAQAAABAVQg4AAACAqBByAAAAAESFkAMAAAAgKoQcAAAAAFEh5AAAAACICiEHAAAAQFQIOQAAAACiQsgBAAAAEBVCDgAAAICoEHIAAAAARIWQAwAAACAqhBwAAAAAUSHkAAAAAIgKIQcAAABAVAg5AAAAAKJCyAEAAAAQFUIOAAAAgKgQcgAAAABEhZADAAAAICqEHAAAAABRIeQAAAAAiAohBwAAAEBUCDkAAAAAokLIAQAAABAVQg4AAACAqBByAAAAAESFkAMAAAAgKoQcAAAAAFEh5AAAAACICiEHAAAAQFQIOQAAAACiQsgBAAAAEBVCDgAAAICoEHIAAAAARIWQAwAAACAqhBwAAAAAUSHkAAAAAIgKIQcAAABAVAg5AAAAAKJCyAEAAAAQFUIOAAAAgKgQcgAAAABEhZADAAAAICqEHAAAAABRIeQAAAAAiAohBwAAAEBUCDkAAAAAokLIAQAAABAVQg4AAACAqBByAAAAAESFkAMAAAAgKoQcAAAAAFEh5AAAAACICiEHAAAAQFQIOQAAAACiQsgBAAAAEBVCDgAAAICoEHIAAAAARIWQAwAAACAqhBwAAAAAUSHkAAAAAIgKIQcAUOxDq2/ceNO31B+/8NVbPrT6Rvn1X/7dZ+UXf776xnWf/+qnPv+1tRu+cuddv0j8raIe+dDqGz/1+a+lH5evI//7tzvucn8xAIDYzWi7AACADpgxNPTIrx4/fOTI4MDAESH2PLZ3xtBQ4jlDQ0Mr33i1EOLg1KHPfmnLzJkzFl90vvk1Dx8+PP7AQ6PnnZP5OgAAVMNIDgDASm947s5fPiKEeOjhPec84+mGZ540c8YrX/obt975k8LXfMWLnv/Nf7/TWREBABBCEHIAAJYuHDn3nvt2CiF+cd+DF5w/z/zks5/x9D2PPlH4mgvn94QQ4/c/5KSEAABIhBwAgJULRuZt37FTCLH9/ocWLSgIOYcPHxkasmpiXvGi59986wmDOdPT02pNzv2TD1cuMACgb7EmBwBg5dRTTh4YGHh87z4hxMknzTQ/+cGHHhk+60yblx0975zBgYHt90+qR1iTAwCoiZEcAICtC84/d+x7dyxa0DM/bf+BX3/ju7e/5PIlli/LyhwAgFuM5AAAbF08et6W793xR3/wu5l/K6eZDYiB6cOHX3L5pXLPtOnp6U9u/MrRZwwMLhw5N/0Pzz/37KGhoUPT0/rryK/n94aXv/gy5xcCAIjbwP6D04mHxif3CCFGe3PbKA8AIFo337ZVCHHVFbYjPAAAFMoML0xXAwAAABAVQg4AAACAqBByAAAAAESFkAMAAAAgKoQcAAAAAFEh5AAAAACICiEHAAAAQFQIOQAAAACiQsgBAAAAEBVCDgAAAICoEHIAAAAARIWQAwAAACAqhBwAAAAAUSHkAAAAAIgKIQcAAABAVAg5AAAAAKJCyAEAAAAQFUIOAAAAgKgQcgAAAABEhZADAAAAICqEHAAAAABRIeQAAAAAiAohBwAAAEBUCDkAAAAAokLIAQAAABAVQg4AAACAqBByAAAAAESFkAMAAAAgKoQcAAAAAFEh5AAAAACICiEHAAAAQFQIOQAAAACiQsgBAAAAEBVCDgAAAICoEHIAAAAARIWQAwAAACAqhBwAAAAAUSHkAAAAAIgKIQcAAABAVAg5AAAAAKJCyAEAAAAQFUIOAAAAgKgQcgAAAABEhZADAAAAICqEHAAAAABRIeQAAAAAiAohBwAAAEBUCDkAAAAAokLIAQAAABAVQg4AAACAqBByAAAAAESFkAMAAAAgKoQcAAAAAFEh5AAAAACICiEHAAAAQFQIOQAAAACiQsgBAAAAEBVCDgAAAICoEHIAAAAARIWQAwAAACAqhBwAAAAAUSHkAAAAAIgKIQcAAABAVAg5AAAAAKJCyAEAAAAQFUIOAAAAgKgQcgAAAABEhZADAAAAICqEHAAAAABRIeQAAAAAiAohBwAAAEBUCDkAAAAAokLIAQAAABAVQg4AAACAqBByAAAAAESFkAMAAAAgKoQcAAAAAFEh5AAAAACICiEHAAAAQFQIOQAAAACiQsgBAAAAEBVCDgAAAICoEHIAAAAARIWQAwAAACAqhBwAAAAAUSHkAAAAAIgKIQcAAABAVAg5AAAAAKJCyAEAAAAQFUIOAAAAgKgQcgAAAABEhZADAAAAICqEHAAAAABRIeQAAAAAiAohBwAAAEBUCDkAAAAAokLIAQAAABAVQg4AAACAqBByAAAAAESFkAMAAAAgKoQcAAAAAFEh5AAAAACICiEHAAAAQFQIOQAAAACiQsgBAAAAEBVCDgAAAICoEHIAAAAARIWQAwAAACAqhBwAAAAAUSHkAAAAAIgKIQcAAABAVAg5AAAAAKJCyOlHazdtabsIAAAAQFNmtF0AeKXijfpi1Yql7RUHAACgWWs3baG304cIOf1CpZobrlmuHly9cbN8nA8/AACIiT5vhXu7fWhg/8HpxEPjk3uEEKO9uW2UB+5lxhvd6o2b1dd8+AE05+bbtgohrrpiSdsFARCnxIT8RM9H7/AI+jwRyQwvhJyYFcYbnfrk85kH0BBCDoAm6NnGps8juMMbF0JOHykVbxRyDoBGEXIAOFetzyPR84lDZnhhd7UIVf60q+ez/RoAAAhfnYRT+V+hEwg50ar5aSfnAACATqiTVeS/pdsTH0JObOSnNPFp37p9Uv/P/ArkHAAAEL7MPk8mm44Q3Z7IEHKikv58Zn6YC6MOOQcAAITMsoti0xGi2xMlQk480tNS1Qd4ycKe/l/ibzOpFxlfs76R4gIAAFRiuRTHviPE4pz4EHJik5lwEs+xzDnK+Jr1RB0AANA6vU9in3ASf2XIOQzmRIOQE4m8aanpD7b58YRlu45/+Ik6AACgLXo/RPZPEod7ZqrQESLnxIGQE4PMpTiiKMnIv80bzMmrOMg5AADAs7Ldj2odIX1xDlGn62a0XQDUUuGI3/pkRTN6/XV+vh0AAOhbefFm2a7JseHe6o2b3fZ/1Kut3rhZ9rI4J7SjGMnpMH3Vnf4Jt1xpU/n5EkM6AACgUdU6G046QqpzxahORzGS00k2Azg2q26WLOzlVQQ3XLN89cbNY8M9ceLKHB1DOgAAoAmF8UZ2UQxqdoQk2ctiVKeLBvYfnE48ND65Rwgx2pvbRnlQoJX5aWp9TiLtjA331CNEHQCFbr5tqxDiqiuWtF0QAOEqjDdnLVqwYe+U/Nrn1s+qO0TUCU1meGEkp0ssd4V3To7qJB6Ud1CO30dJjeRSBQAAgFJUwtFvpOrGhnti75Ro42SbzO4QgkXI6YZWBnDSzlq0YPe9O1SwySuJrALWbtpCzgEAADaOdnW0SWiJOfNtDeDoZM6hh9MJhJwuCeE43sKEI7RbHUxgBQAAmdKr+TO7Fmrw5Frj04AE1uR0QN5Bnz7p47P2JWH2KgAda3IASGVn4FfrhzREFoa+TTgywwtbSKNY5ZqFQ7UAAIBufM36CmuME6dlAIUIOaFrfRhHJZxq9Yv+r8g5AAD0LRlvbOa95wkk56jzc9ouCExYkwMTPeHUeR21SkftmsKW0wAA9AN9wzT5Rc1OxeqNmwNJOwgZISdorQ/jSJkFSByeZXPklo6DRAEAiJt+4o19wqnZwfCDbdbCR8jpAMOm7I3mH/l9098i82xg+WC1qCNIOwAAxMJwmqe53+Kwg+EEp+J0GiEnaObbA61MBlUVUKK6kY9v3T5ZrRpiYAcAgK4zxJtCpToY3masMVDTXWw80FUy4TR3jyFzGCevAtIfybwNY2l8zXr5X+VXAAAAntk03/JMz7x+i30Hw9scfv3EP3QRIaeTKuy96FDeWI3DoWSiDgAA4XPbXpfqYDQ9l4xjMLqOkNM9HhKOYRjHnGTk39YZzNExsAMAQIDcNtBlOxje7vByDEanEXI6pt0xnDpkgceGe/p/lv+WqAMAQAiqtcilGn0bslPhZ2MAck5HDew/OJ14aHxyjxBitDe3jfLAxE/CKbsaJ8HymfK7yBm6ZbE/AdBRN9+2VQhx1RVL2i4IgHKq3Wo8a9ECIcSGvVPyj+YTKcp2MFwd5WdJD1TsRhCazPDC7mqd4TPh5LFZdbNkYc9+upqs/nbfu8PwnIx7P9qtFCoaAACa4yTeiKLeS4UOhjpn3A997IjjcTqBkNMNnhNO+ruU2lSg7A4EsioUWWmncHRb/WSobgAAcOKEeVlZDXHeRAzVoOvqxxvzk71tJy27SfQ3uoKQ0wF15oDaf/I9D/tm3oBJDOzYn44sTx0WVD0AANRg2eUYG+4lck5mvGma6ktU68OU7SPRx+gW1uR0iV715H0sC4du0/9Q/yc+9zOQ3/faOTMz/9Y8hdfwghI1ERAg1uQAIZPdDJtmVzW4eY24JJtyzyfbSJW7SXnoV4QsM7wQcjrJcKPFsJT/rEUL9NmxaZ53bDOEnAoJJ/GyVEZAgAg5QIDG16yXUyfKDoPILww5Z8PeKf+bwZpjjKGblLmtEctvOoGQE6HEZ69wdWBiNNl+RWAT8kJOnYQjUvu2sRUbEA5CDhAO2WewnxmeyRB1PA/jJOhRR5XNvNGRoM/QWeyuFqHE3QX54TREHfnxTk+cDefUHVknznxgx7zHd3/5Qz86PD19yauuWvSiy9UTHvjRXTd/7JNvXf93li+ofhrUXAAA3PYXf/PQw7sGBwaOHDlyztlni+GemJ5e8qudX/2rv506cOAFK15z3vMW27+aWhWzYe+UeeqaZ6pgslTEmz5EyInQ6PXXmYd05Ee95s2bJsiEM/TIrvlPPb78f9xw0qxZB596avNH1jxt7pkPz5wthJj+9cG7N/6LGByo8OKkHQBA35KN4GOPP77rkUeec/GzZgwNHZqe/tnddw8N7x569NFnPO+ixa9e+tRjj3/5Q3/9plTISZwMkdjiTO2tLBvxcKKOzDkb9k4VHspHxyBKhJw4FQ7pKO2OI+tVoZqltvDJX132+68/adYsIcRJs2bNfelLvve5f73ozdcKIR4Yu/ns37rivn+9SVa4ZfeqlvQfC/UaACBW6W7AzocmR+bPnzE0JISYMTQ0Mv+8GT/Z9uALf/ubjx9aLMSjD04ODg3pz888+C6zCfZ8ao0rdAMiRsiJWWHUCWcMR7nhmuUbrv/W3JHz5B+3bp+c1Ttn/65Hlizs/fLue3cdPnTl6666/6avqr+tlnMUhncAAJExtPv7DxyYPWuW+uPsWbOf2v/UkZkzhRC3fOLTEz/44bI/fbf6W5VwEk2tfDzdBKuRE3kH89o5M83bHbWLdj96g20XAI3L/BgXHrLZqLxhnEToOlq9HhED04empw7d/n//34veeo38K1WxZt5kqmB8zXr5n5NXAwDAs2oN2fThw/KLK9/91pe95233fO/78o95CUeUbILbHd6R/Yp0n4eE0w8YyekL9rPXQnDmub3d990/fOFC+cdzBqcenHfOxO13Htx/4Nt//09CiKkDv77lHz595bvemlm9yjtJiRqtcD6uwmQ2AEBXlG3ZZ5166r6n9s152hwhxNhwb+hXe0467fST7/rxO//yvwsh5j9v8Xc/+Rn9+XnTJZYs7NkknAAHc2jZ+wchp4/YRB15x8XPNLbZI/P2TexMP37pa5bfvuGfz/29FUOnnHzxOWeMfXTDpa9dft7zFi88tsfaZ97+3ivf9VZxrJLNHDFXX9e5h8RkNgBAgCrftXzo2Yv33P2zA5ePHpk5892ve/HYRz9x6dvetP22O3bc8aPzf/P5u+4ZP/2cYZGz6iYhswlOzFibPTJPbJtYvXFz0/0Km94LTXm/IeT0HbX3mqoLPA8ly2+3cvGIkNWfEOu2Tejl6V1y8b5fPXrHpz8jBgd/uHuPEOKJh3dX/nZqYOfaOTMLd5DMk5d2OCMMAOBN/RkZ02c9Y2r//gV3bx0YHNy45etCiCce3n3Z773uO2tv/Mnmbw/NmPGSd77FRUmPtu9CiJWLR2Qr74GhPzM23FvlpxAIBiGnH8mpXHpdoGZzqb9q+qbLvomdqgZM2z9vwXPetVIIsWRh78DeJx994IQx8bd86mOJ51vuQKAfEFQt8KhjoZW1m7aorwk8AID6yp70bXbC4Xh7pw6dN/933r9S/km2sE876+lX/9mfqKeUXexqboLllI1G+xWqP5M5NV3endQba/SJgf0HpxMPZR4aipio2jNRb3o4OSe95cDskXmJkRxhN1Be6snp76sUpp1Eqsn74SRuIBF4gLSbb9sqhLjqiiVtFwQIUamOeOFa0/TB3yJnm5+E+k1w5vZCjd48ld8x/TNhilqfyAwvjOT0I9X/zlyl4+Feiy6dcETJA3Bq7iKtmoHMtGMf/Nqa/gcA6C492Fi2v7KVGRvuZeaczGyjK/wuDTXBjS76VVPT1c+EeANCDnyM5Kp+f1sHISeWQmZKT2arM7TFLm0AgDzH24jhnijZyqhjN1WfvjDYSJ43OtPbXPnFhr1TTe9vNDbcYyYFJEIOhNASThP1jmGqWGg7SypHGwyLYX0bBB4AgMODHPSc09bdQwNVvMS9xUajjvqm7AkEiZCDBhOOeQBHJRw/O1aXVTmApQfNdYlGjswDALFq9Hi6vCARCEPxykYd+00L1DcFBCEHStmkYVmPFNa8fhKOYTQpk7cARuYBgGh4PnS7KzknUyLqmOnPMbfL8psymANByEHZpTj290jMFW6wE9VEUcJJ7K1pueYyb2AngcwDAB3SaKqxaW46kXMMZVNRJ/GEvI1Px4Z7qh+S2UarvyXngJDT1/SEYxg1TgQbQ2e97NrHMCeqSemyZR4dYNhqM7H3tGXO0ZF5ACAofsZqSjU3geccyVw29VeFhzrox/pl3nUl2EDhnBwcZxjVWbViqX3Nbo46rSSc1Rs3W1b9ecVTTU6igcl7PDGHOG8L/zrIPOgczslB5zhMNYk7X0rN5kaynJVtc06OczY7rNqf0J1u+xi0QWZ4IeQgV/0TlyufROaW/YKcsgnH5m8TxXCbcxRV6VPXI2SEHHRCQ8M1Yxa7RVdubkIOOSI/59hnG4UbfEjjMFCUk+grZ54caiYrLz3qtLgUZ/bIvH0TO22emVf752WYJQt7mVMLMqVP43FifM16dY8wb0SO8AMAaWs3bWno9pPQ6vxS6aJCc2NzHFyL0psQEG/QNEIOylFVjH3aURVZnbM1nZg9Mk9+YZl2JMOqG0U2PFu3Txqelm6BEiNdlTOPzQ+WXTUB9DnDlGxVi9ZPO5ZrUzO5am7SVPMntk1ULp4TZBt4Q8hBRRUGdqRWpgIn7mxlpp22BvGVCpmnVG7U71bSZgDoH0ebqqLZYvKIM/VHy8Bjk2raal+OZ5tjVi4eWbdtwv7kGYfMh8hloqlCHYQc1FJhYMcnffhC5Rm90j+hAci6v2U/D009v9RgjoE585QdFktMFUj/vmhLAMShcnuU2C0mb3inzliNgavmJh1spFJTGNpFewQnCDlwo/LATnPyljlmph0zm1kBpVbmVJC5tKnsrTjDLbTM3x0tDYCQ2Tc6Nov+dfKZsh0ZG+7VWejiZDVO4jn2zU1etmllMKcQjQ4cIuTApcKBnbwq1Xlta7NhpV715wWeUpOeSz25vrI/sczDp80zBxjwARAO//fRMqvNhtRvbmRp122bMEcydf6m4Xy8Oio06LQsaAIhB41ID+xkng+gNx4Oc45NwklYt21ChH04qVJzh7r0L6LUDGkGfAB4UCfP5B1HU03gu5ZVdu2cmbI1cXuTUba/euNufnGaDzSHkIMGZQ7sJO6Kye712HCvxYTTIYUT1RJzGBJ3+2RrnT6ltCYGfADU4eHATZFVbZorzIQoc45wPaSjxr5U465amRuuWa72HuBIA3hAyIEPo9dfJzZtETkHYjq86xZ3wlEym6LMKdrpDUkz/22pwRwblQd8OMwUiJufKWeF/XXLClO9mmxcupJzSpWzoSEdSbUsetoB/CDkwB/VeU03ck4q1vATjuWJ1HkME9XyjsGWjxv2fFONt/Ock1Y4fVEi5wDdYjh/pulaJcFyd4EKFabPxTl1VCun2yGdzK2i9Vrd8IYBHBrYf3A68dD45B4hxGhvbhvlQR+RXd5SO97Y1N0VIoS3EwzqhBzDRLW8Btvmb/WCJcpW+XBSM/Pm17IkhJxY3XzbViHEVVcsabsgcKmwz9po1EnvPGmuzOtUmJXrcJ/n5NS531e45rNUYy1/78xehgeZ4YWRHLTmaMW3aYtNpanHG729bOi8gmAZflZ5GcZms9HMm3/pn23N2GN/to9+bqmOxhJoV3ocvvBGlTpwxknUMdT5TnZqtqkwA5+0VmfQKXFd6fPZLId6WHuDEBBy0CbLMWtVX6fbSFUFV047bR1EXUrhRDXzelnZbJsPKlXfyNB4Z/6QbZKPfbwxTJ8bG+4tK5rNTwoC6mhiwYw6cKbsnNgm7mHVrDC7MmlNqhzG8mr1xF4CgbebACEHLTPXknkDOGn10443iTN57E+hbrRFqdx4mwd87OONoSTqRQo7SeYuGhEIqLk1c+a2MTafbnVrX+RU5jWr7gBvV51Q1W+b8Pmtq+2UYDlWbxl1ZBlYY4kWEXLQGvMwjn28SdCr6cJWs5V50gmVM4/I2SDI/HwPJ5ae8GOv8RNOBKT6GyQUdu+qpSBacYSjub3L5OexzmaY+pCOaGOHmKYrzLxDpZUmti/LY3nfqvIkZEZ1ED5CDtqUVy2qqln2HSs32wEO71w7Z6YeY9KNYoXMY9MM20w0d65yhlTNs/5vPWwEZz8QlIjo5By4Yrj7U7M+rCNvSLZCr11FnbZWtjisMAtTjarAG92m2Szz51x/XxlZH64SQgixdtMWQ6CiekRb2F0N7bBZjZNZLdZs4Mvuw+OK5Z48eU3mum0Tovmi1tzhOq3UTkdSYf/DsECraYl72Oq6EplcR+uewO5qhcx1o/+3vVR2a2apcEdHz7WNE7LkKxePZP6t+bZU4WnOziV+zjWzjXmsm+oOLcoML4QcBMeyoqx/O7PU7tV1VN7QU88867ZN+Cmqt26H4UapOeq0knNsdr7Wy6MnIsty+l8y5L9T0g8hx6ZqyhuNNFRKrcf7UncrdHkfZ7c5p62QU2qCsfCec5y8bVjNiPARchCnamkn/IST4KcJd9jtsEw4mYfxpR+3KWdDB/sIi+0TEj2J9LoFPx1T+76IPlyQmXMayj9uQ46hkJXL72EyWOLtkcjG5r2Y0//EucTkXptOebWPs7faxq36xW4l51R4z5Bt0CGEHESuVO/Ec8ip35DHFHLqn14qyhe1cgSy3CAuPSVd3y9BamuuUYJ68+d1misMQ/mnCpkuoSFFtC79dkq8c1xtOGlgv0axTsKx+dtuVY+SkzL7zDllQw7ZBl3EYaCInF41t7I2N835vPOusOlz1DmMr4LCjl06BZXa/1pmBvV//XHhYms4JxLZPnMvB/2q3R7j6Eoiw+SVMDNFtHgherHT7xBhtyTd5u3kfJ8Vm/e/549z17W4D0Emgg2ixEgOIpeXdsxz3520Oq4mqkndGskpHMYp3GCg8GlNB0jnt1pbXFMhjIFNL1jm09oteYJhJESfK2i+TA/lTKhwYJSZ2+olk/3GIXU+zg4HRjo0kiM5rGQMzZZhJIdsg2gwkoN+pCpxm7Ed1W+ok3MSk0/6cBgnApadj1Jbw7V4Vrq5h62P52Q+LXG8SbsbfOlF0r9WxcvjYQvyPKUSjuWbqtppj3ELZFTEnj6eox6scAnyn9ufV0O2QZ9gJAf9SAYe/Y5v+ma2ZUuT7rY21OHwcKvSsDVqqR2EKq/GKfvM5gZzCn/aNbeGyyxzQxsn2K8pSs+1Sz9HftHi/t3m4oVwCenZYpYf3tY3KEuw/xTU/DhXuIr0bvtyn33RqZWWaer2iq7wivSxmryhTjZ3RtzYeAA4QeI8CvNcl0weZoxIPueq5Z3/kJaXfOrPVbN8clshp87WcI32SmsuK7JReaemOtxehTnnOF/QUjbhlH1TNfSOcjhXrfDJ5ksoPHBT8XOemPC42NJ+Plvig5lYWScIOYgd09WAbKtWLC27UUFiKfPuXUI00D3ySTXb6eiS18lIP1444GPZH6rwZIeqJRyhrbHeun3SPMuooSlGFTb/FeXPYxVCjA33vE6RqjQSUjjRy/dV5Kv5pmpLEx9n+0iTV9t4mLTW6KdYv1Wx7FhcsZ+KJqlI09YUWSAEhBz0NdUSHJ+jbDxuXMq7E6w3Tp0OPAmZnYnMvsjRB4/NG4lY+HtJldr8N/1gYULwJnMCT0LZCwlzQUu1N1WjHW4PbAaQLafLhrZlmT3DVFV9ikHhdaUX28g2bq1FuwbEh+lqwAlkY+B8Tn+dzONtNU7NTpIeezo9b6RPtoYLdtKdrtELYYOyPP43K9NDTqkVgGl+jqCp+TOvsADP8khipqWhP2WGl8GWCgOEqKGEI4TYfe8O/b86hQzWvomd6r+2ywIhqi4ZV48UDknZjLHUUfMkysILUS/b9IV0lM8hO4e1h58RLfnmsX/n1G8CVKPDDDTAEiEHsLJ642aH+zLZN3hdGcbpB2XnoZmnGIkA+taG+VHmf+hzLlDNkyjrv3ijnLypnL+d4qgN2g0DTdzY0nMOUQcoxJocoJhqTvSZAGX3KjBINIExredplD7Rxdvwkc366XBW5mSymR8lL6FwsXtzS0Hsl+I4uZAm2N+hCO1NNXtknlxZ1/TilobusPhZnJNYDdXcEL2+0maVEOLYpIPMnLN20xZmrAESIQfIlm4/Ei1HYolnU5nHeL5hTd62wPbAvCmTfQQydEw7sTWcN352IGh9pKVprt5UZbcfKNzEbOXikXVd3kHE5yYEzuNN4WGdq1YsZS8BoBAhBzhKtRmZ4zaF9GbJVeApdWhPKU3HG9nD8LPH0b6JnYU9tsIn9M86ogrzo8IMbNFcSBPsN2LOoz4RndupTJGVm6yIRPCBuTDYJDBcAxQi5ADHuWo2mhvkqSmmoRt9okthRCmRgrp899peaPOj0ixzcv0LaW5IymfUVyzjjU2q7+6OzDpV16nfciDXUjbVACiLkAMc1dyNsSYyT6luh96HiyDeVGDu0tW/7d0h0Uy6c3sh3T1nRnK+EbOkck5DfB7ykxjYEdZpx1XGI9UAnhFyAN/sM8+yXZNjWWtyZCNtOQcjptGbhujdQZ933513SRGItgYGm3sXdXowR6eijrC4KFV5VpvwRqoB2kXIAVpWmHn0lrjsvBp92+vdu44/3vUN3Lq+7XX69+hwEQVqcjiy52f5fqMfh6YHc/xI7A2w7NiKR5vwpm42ZT5ZP1GAVAMEhZADhCXZTGpb6CQO6skc5NEZDvbJ3A7IYfJp9HifaA6IULHESa/6hBfxOIDQ4GQ/v8Mgbi9Ez5xxDIN05Sos9zozRxfDk8Wxmk1+TbABgkXIAbohM+HY9Dnsjy5Ndw5CG/DxM/XO/3rx+oMwfbWsyK3MzNyhYTEPo5r6DgTC9c2Lmsty6mzfXJhzZNnGhnvLdk3qFW8091mAuBFygKDJ8xAydrUuOiRB/hP7hJOp6QGfUlhcZNChTrk9OdfLT9q8ds7MKH+GrpRaytKQJk7btBzPUcM1+lmcAAJHyAG6odTmb43eaPQ/4BNZvPFwG9jnOopOZwNvv4uGgoHnxWmNDukkNBFpMpWatyZxFifQCYNtFwBAsWoJZ9WKpX7mi+++d0fiP4cv3krCkd+riR6wz8tptAfvc8ZO09/Lz1srjjlO186ZmT55xonm6pA8o9dfJ/9TFaz9Fa1asZTjOIHAMZIDhK5ywpFfpHNOOIeTmkU2gCP8XlGjgzneLsTDVfj8XXRl7X4ht0M6+tIXN+XLYr7jowZnSv2OyDlAyAb2H5xOPDQ+uUcIMdqb20Z5AFiR7bHeGOv3ICs0vQ6Tj/2mCAatJxznG8T5v6KG9riL40LaugrRwJuqxbsAri7KyRpCpfIIdmISmr6LGnkGCFlmeGEkB+gelXASkyvqNMN+BnzK3smWx/uEtslbBW1NumtuGMR/x7qJYZBWfh0eFrR4IGeUlTpwpqGBLIeTcvUqVN/xBUAXEXKArmr6/mJm16FO8pEFtunhJfoW5gn64Uegdkel3PYsW+n2OZ/u1VbnNYQ9yuyVPXDGQP3AM6/afhjH56E0icDj7fsCcCUj5Iz25o5P7hmf3MOMNSBYbc2dqDzgY9+tNJxhmqmwK9ZuCmo34bgdzGnxWpoYlWprllcgS3ScL+63vBz7qw7nnE3mqgEhy1tok7Emx/BsALCRWDKk55bCFTtuZ+cXyotArtaBBLJqwtWFiIiupd0NLdyuZsm8Fm+7MItjk9ZEzuWoD3Xm01j0AqCOvNjCFtIAmlVqZMb/PKL0/tfOd7CNZnc4Eca1xLFSwu1Psun3cCH16Tb/dvKeRsIB4Fx2yJFhSAYjAChLdllWb9ycOLTHPP+k7ES18MXRHQ9HCBHLocgup/Bjm3koDZ8RAHUYZp+x8QCAxpW6TZt4cldO9ckjN4gzaHrJkFwBUnP5RwjzuzrHaixluBf+DgR5Mu5Z2B01ox9K01jpAPS7gpDD9gMAqlH9GMuEk9fdMQ/+tBKB7BdY27xa/WlF4e8v55CTzGbDz3Qvm63JRHtbFJRd+m9/pKZ6JgBUZp50lhty5B5rDZQHQB8pm3DKTs0v7IQ5T0H2G2ELX/PuirvjFt3oPuR51YqBIRKYN1+uqYntyyrkHBbkAKgjbzzGNJLDXtIA6rDpu1SON5baGgiKch5OKKkgrsxmOZgjKuWcVnZhlp9lm8M0Gc8BUFnhXtBWa3LIOQDcajrbWDJ0AVcd66Wl97q17JVGtn1CNJcTJnOAyXvLhbz5siqVOcaEWXgAgbOZblawhTTZBkBDVq1Y2q3+jQpmaoeovBvV3RrG6VZpxbG4ZS52ty7KZl8y+UW3rkvq3CcdQFeYc0r2YaAJnA0KwJW1m7Z0qMejTjVNDz0lDjxVyt5c97N3Qt4ZrHqn2bwsJKiRHMORsuFcUampYjZvJzUkIp8W8jAOADTHMphYTVdTi3NsXhEADDrdJyssfIUb7fVXTXR9l23PLH9HnlezGFanqHed/Zp+AIiSmqVmk0esRnIqvC4AxEF1PRMJJ3HrXe86BxjkEoMAkn76qnmoJ6hhHFE0MKWvYKk/1OZN+neUWVQ9CwV4FQDQkLJJpMRhoGpTaYZ0AEAXyD4KBoZBgKNlzhpG0JchNV7EMjK3hVBGr79u1bEwkLl1RJi/Jn1TMgZqAEDRtxmwDyAFGw8kjPbmqpdWE9gAIGKy62noFoefcKRE8Qq7+524LsPcs3SxO7FqXy7TX71xc15p9dlrHssFAC3Q44YeQ2yUmK6W+JaJRxjYAdBvujhxKLHwQy/22k1b0rPvQr6uwoX4+hM6cUW6vHmS6m+7ciEAUJaToFEx5BgKAQB9YuzWO4UQy37r+W0XpARZZilRcvlXeh4I/9L0y5EyLyrvb8M3duudnSszALhSZxClbshRSDsA+k1HO6Cq3x9NHjAkN5F/vQCAMDmZIOYs5AAAuiJzslMXZ98psvB5M7vkF527KABAZeU2HgAARCCzu9/pFe2GMhduHQEAiA8jOQCAo1jODgCIAyEHAAAAQFSYrgYAAAAgKv8fxcaY9YB2njkAAAAASUVORK5CYII="
    dental_arch_image = tk.PhotoImage(data=_chart_png_data)

    chart_box = tk.Frame(f, bg="#F7FAFD", bd=1, relief="solid", padx=8, pady=8)
    chart_box.pack(fill="x", pady=(0, 8))
    selected_tooth_label = tk.Label(
        chart_box, text="Selected tooth: none",
        bg="#E5EEF7", fg="#17324D", anchor="w",
        font=("Arial", 10, "bold"), padx=10, pady=5
    )
    selected_tooth_label.pack(fill="x", pady=(0, 5))

    chart_canvas = tk.Canvas(chart_box, width=1100, height=470,
                             bg="#F7FAFD", highlightthickness=0)
    chart_canvas.pack(anchor="center")
    chart_canvas.create_image(0, 0, image=dental_arch_image, anchor="nw")
    chart_canvas.dental_arch_image = dental_arch_image

    tooth_markers = {}
    selected_tooth_number = {"value": None}
    upper_numbers = [18,17,16,15,14,13,12,11,21,22,23,24,25,26,27,28]
    lower_numbers = [48,47,46,45,44,43,42,41,31,32,33,34,35,36,37,38]

    def set_tooth_selection(number):
        selected_tooth_number["value"] = str(number)
        tooth.set(str(number))
        selected_tooth_label.config(
            text=f"Selected tooth: {number}  |  FDI quadrant {str(number)[0]}"
        )
        for tooth_no, marker in tooth_markers.items():
            active = str(tooth_no) == str(number)
            chart_canvas.itemconfig(
                marker["circle"], fill="#1769AA" if active else "#FFFFFF",
                outline="#0F568F" if active else "#7891A5",
                width=3 if active else 1.5
            )
            chart_canvas.itemconfig(
                marker["text"], fill="#FFFFFF" if active else "#17324D"
            )

    def add_tooth_marker(number, x, y):
        circle = chart_canvas.create_oval(
            x-17, y-12, x+17, y+12, fill="#FFFFFF",
            outline="#7891A5", width=1.5, tags=(f"tooth_{number}",)
        )
        text_id = chart_canvas.create_text(
            x, y, text=str(number), fill="#17324D",
            font=("Arial", 8, "bold"), tags=(f"tooth_{number}",)
        )
        tooth_markers[number] = {"circle": circle, "text": text_id}
        chart_canvas.tag_bind(
            f"tooth_{number}", "<Button-1>",
            lambda event, n=number: set_tooth_selection(n)
        )

    for index, number in enumerate(upper_numbers):
        angle = math.radians(200 + index * (140 / 15))
        x = 550 + 410 * math.cos(angle)
        y = 145 + 115 * math.sin(angle)
        add_tooth_marker(number, x, y)

    for index, number in enumerate(lower_numbers):
        angle = math.radians(160 - index * (140 / 15))
        x = 550 + 410 * math.cos(angle)
        y = 325 + 115 * math.sin(angle)
        add_tooth_marker(number, x, y)

    grid = ttk.Frame(f); grid.pack(fill="x")
    tooth = add_combo(grid, "Tooth Number", 0, [str(n) for n in range(11, 49) if n % 10 in range(1, 9)])
    dentition = add_combo(grid, "Dentition", 0, ["Permanent", "Primary"], 2)
    surface = add_combo(grid, "Surface", 1, ["None", "Mesial", "Distal", "Occlusal", "Incisal", "Buccal", "Lingual", "Palatal"])
    condition = add_combo(grid, "Condition", 1, ["Healthy", "Caries", "Filled", "Missing", "Crown", "Root Canal", "Fracture", "Implant", "Extraction Needed", "Other"], 2, 28)
    tooth_notes = add_entry(grid, "Notes", 2, width=55)
    dental_tree = add_record_table(f, ("tooth", "dentition", "surface", "condition", "notes"),
                                   ("Tooth", "Dentition", "Surface", "Condition", "Notes"))
    def add_tooth():
        if not tooth.get() or not condition.get():
            messagebox.showwarning("Required", "Select a tooth and condition.", parent=window); return
        try:
            with get_connection() as connection:
                cur = connection.cursor()
                cur.execute("SELECT ToothID FROM dbo.Teeth WHERE ToothCode = ?", tooth.get().strip())
                tooth_row = cur.fetchone()
                if not tooth_row:
                    messagebox.showerror("Missing reference", f"Tooth {tooth.get()} was not found in dbo.Teeth.", parent=window); return
                cur.execute("SELECT TOP (1) ClinicalVisitID FROM dbo.ClinicalVisits WHERE PatientID=? ORDER BY VisitDateTime DESC", patient.PatientID)
                visit_row = cur.fetchone()
                if not visit_row:
                    messagebox.showwarning("Clinical Visit Required", "Create a Clinical Visit for this patient before adding a tooth condition.", parent=window); return
                surface_id = None
                if surface.get() and surface.get() != "None":
                    cur.execute("SELECT ToothSurfaceID FROM dbo.ToothSurfaces WHERE SurfaceName=? OR SurfaceCode=?", surface.get(), surface.get())
                    sr = cur.fetchone()
                    if sr: surface_id = sr.ToothSurfaceID
                condition_id = None
                cur.execute("SELECT ToothConditionTypeID FROM dbo.ToothConditionTypes WHERE ConditionName=? OR ConditionCode=?", condition.get(), condition.get())
                cr = cur.fetchone()
                if cr: condition_id = cr.ToothConditionTypeID
                cur.execute("""
                    INSERT INTO dbo.ToothClinicalRecords
                    (ClinicalVisitID, ToothID, ToothSurfaceID, ClinicalCondition, ClinicalDescription, ToothConditionTypeID, RecordedAt)
                    VALUES (?, ?, ?, ?, ?, ?, SYSDATETIME())
                """, visit_row.ClinicalVisitID, tooth_row.ToothID, surface_id, condition.get(),
                     tooth_notes.get().strip() or None, condition_id)
            dental_tree.insert("", "end", values=(tooth.get(), dentition.get(), surface.get(), condition.get(), tooth_notes.get()))
            tooth_notes.delete(0, tk.END)
            messagebox.showinfo("Saved", "Tooth condition saved to dbo.ToothClinicalRecords.", parent=window)
        except Exception as error:
            messagebox.showerror("Database Error", str(error), parent=window)

    ttk.Button(f, text="Add Tooth Record", command=add_tooth).pack(anchor="e", pady=6)

    # 5. Clinical Visits
    f = tab("Clinical Visits")
    ttk.Label(f, text="Clinical Visits & Treatments", font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 10))
    grid = ttk.Frame(f); grid.pack(fill="x")
    visit_date = add_entry(grid, "Visit Date", 0)
    dentist = add_entry(grid, "Dentist", 0, 2, 28)
    diagnosis = add_entry(grid, "Diagnosis", 1, width=55)
    treatment = add_entry(grid, "Treatment / Procedure", 2, width=55)
    visit_cost = add_entry(grid, "Treatment Cost", 3)
    visit_status = add_combo(grid, "Visit Status", 3, ["Planned", "In Progress", "Completed", "Cancelled"], 2)
    visit_notes_frame = ttk.Frame(f)
    visit_notes_frame.pack(fill="x", pady=(10, 0))
    visit_notes = add_text(visit_notes_frame, "Clinical Notes", 0)
    visit_tree = add_record_table(f, ("date", "dentist", "diagnosis", "treatment", "cost", "status"),
                                  ("Date", "Dentist", "Diagnosis", "Treatment", "Cost", "Status"))
    def add_visit():
        if not visit_date.get().strip() or not dentist.get().strip():
            messagebox.showwarning("Required", "Enter visit date and dentist name.", parent=window); return
        try:
            with get_connection() as connection:
                cur = connection.cursor()
                cur.execute("SELECT DentistID FROM dbo.Dentists WHERE FirstName + N' ' + LastName = ? AND IsActive=1", dentist.get().strip())
                dr = cur.fetchone()
                if not dr:
                    messagebox.showerror("Dentist not found", "Enter the full name of an active dentist as shown in Manage Dentists.", parent=window); return
                cur.execute("""
                    INSERT INTO dbo.ClinicalVisits
                    (PatientID, DentistID, VisitDateTime, Diagnosis, ClinicalNotes, CreatedAt)
                    OUTPUT INSERTED.ClinicalVisitID
                    VALUES (?, ?, ?, ?, ?, SYSDATETIME())
                """, patient.PatientID, dr.DentistID, visit_date.get().strip(),
                     diagnosis.get().strip() or None, visit_notes.get("1.0", "end-1c").strip() or None)
                visit_id = cur.fetchone()[0]
                if treatment.get().strip():
                    cur.execute("SELECT TOP (1) DentalTreatmentID, StandardFee FROM dbo.DentalTreatments WHERE DentalTreatmentName=? AND IsActive=1", treatment.get().strip())
                    tr = cur.fetchone()
                    if tr:
                        try: qty_cost = float(visit_cost.get().strip()) if visit_cost.get().strip() else float(tr.StandardFee)
                        except ValueError: qty_cost = float(tr.StandardFee)
                        cur.execute("""
                            INSERT INTO dbo.VisitTreatments
                            (ClinicalVisitID, DentalTreatmentID, Quantity, UnitFee, DiscountAmount, TreatmentNotes)
                            VALUES (?, ?, 1, ?, 0, ?)
                        """, visit_id, tr.DentalTreatmentID, qty_cost, visit_status.get().strip() or None)
            visit_tree.insert("", "end", values=(visit_date.get(), dentist.get(), diagnosis.get(), treatment.get(), visit_cost.get(), visit_status.get()))
            for w in (visit_date, diagnosis, treatment, visit_cost): w.delete(0, tk.END)
            visit_notes.delete("1.0", tk.END)
            messagebox.showinfo("Saved", "Clinical visit saved to SQL Server.", parent=window)
        except Exception as error:
            messagebox.showerror("Database Error", str(error), parent=window)

    ttk.Button(f, text="Add Clinical Visit", command=add_visit).pack(anchor="e", pady=6)

    # 6. Appointments
    f = tab("Appointments")
    ttk.Label(f, text="Patient Appointment History", font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 10))
    grid = ttk.Frame(f); grid.pack(fill="x")
    ap_date = add_entry(grid, "Appointment Date", 0)
    ap_time = add_entry(grid, "Appointment Time", 0, 2)
    ap_dentist = add_entry(grid, "Dentist", 1)
    ap_reason = add_entry(grid, "Reason", 1, 2, 30)
    ap_status = add_combo(grid, "Status", 2, ["Scheduled", "Confirmed", "Completed", "Cancelled", "No Show"])
    ap_notes = add_entry(grid, "Notes", 2, 2, 30)
    ap_tree = add_record_table(f, ("date", "time", "dentist", "reason", "status", "notes"),
                               ("Date", "Time", "Dentist", "Reason", "Status", "Notes"))
    def add_appointment():
        if not ap_date.get().strip() or not ap_time.get().strip() or not ap_dentist.get().strip():
            messagebox.showwarning("Required", "Enter appointment date, time and dentist.", parent=window); return
        try:
            from datetime import datetime, timedelta
            start_dt = datetime.strptime(f"{ap_date.get().strip()} {ap_time.get().strip()}", "%Y-%m-%d %H:%M")
            end_dt = start_dt + timedelta(minutes=30)
            with get_connection() as connection:
                cur = connection.cursor()
                cur.execute("SELECT DentistID FROM dbo.Dentists WHERE FirstName + N' ' + LastName = ? AND IsActive=1", ap_dentist.get().strip())
                dr = cur.fetchone()
                if not dr:
                    messagebox.showerror("Dentist not found", "Enter the full name of an active dentist.", parent=window); return
                cur.execute("SELECT AppointmentStatusID FROM dbo.AppointmentStatuses WHERE StatusName=? OR StatusCode=?", ap_status.get().strip(), ap_status.get().strip())
                st = cur.fetchone()
                if not st:
                    cur.execute("SELECT TOP (1) AppointmentStatusID FROM dbo.AppointmentStatuses ORDER BY AppointmentStatusID")
                    st = cur.fetchone()
                if not st:
                    messagebox.showerror("Missing status", "dbo.AppointmentStatuses has no status rows.", parent=window); return
                cur.execute("SELECT ISNULL(MAX(AppointmentNumber),0)+1 FROM dbo.Appointments")
                ap_number = cur.fetchone()[0]
                cur.execute("""
                    INSERT INTO dbo.Appointments
                    (PatientID, DentistID, AppointmentStatusID, AppointmentStartDateTime,
                     AppointmentEndDateTime, AppointmentReason, AppointmentNotes, AppointmentNumber, CreatedAt)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, SYSDATETIME())
                """, patient.PatientID, dr.DentistID, st.AppointmentStatusID, start_dt,
                     end_dt, ap_reason.get().strip() or None, ap_notes.get().strip() or None, ap_number)
            ap_tree.insert("", "end", values=(start_dt.strftime("%Y-%m-%d"), start_dt.strftime("%H:%M"), ap_dentist.get(), ap_reason.get(), ap_status.get(), ap_notes.get()))
            for w in (ap_date, ap_time, ap_dentist, ap_reason, ap_notes): w.delete(0, tk.END)
            messagebox.showinfo("Saved", f"Appointment #{ap_number} saved.", parent=window)
        except Exception as error:
            messagebox.showerror("Database Error", str(error), parent=window)

    ttk.Button(f, text="Add Appointment", command=add_appointment).pack(anchor="e", pady=6)

    # 7. Images & Documents
    f = tab("Images & Documents")
    ttk.Label(f, text="Patient Images & Documents", font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 10))
    grid = ttk.Frame(f); grid.pack(fill="x")
    doc_type = add_combo(grid, "Document Type", 0, ["X-Ray", "Clinical Photo", "Prescription", "Referral", "Lab Result", "Consent Form", "Other"])
    doc_title = add_entry(grid, "Title", 0, 2, 30)
    doc_date = add_entry(grid, "Document Date", 1)
    doc_path = add_entry(grid, "File Path", 1, 2, 45)
    doc_notes = add_entry(grid, "Notes", 2, width=55)
    doc_tree = add_record_table(f, ("type", "title", "date", "path", "notes"),
                                ("Type", "Title", "Date", "File Path", "Notes"))
    def add_document():
        if not doc_title.get().strip() or not doc_path.get().strip():
            messagebox.showwarning("Required", "Enter a title and file path.", parent=window); return
        try:
            kind = doc_type.get().strip() or "Other"
            if kind.lower() in ("x-ray", "clinical photo"):
                with get_connection() as connection:
                    cur = connection.cursor()
                    cur.execute("""
                        INSERT INTO dbo.DentalImages
                        (PatientID, ImageType, FileName, FilePath, ImageDescription, UploadedAt)
                        VALUES (?, ?, ?, ?, ?, SYSDATETIME())
                    """, patient.PatientID, kind, doc_title.get().strip(),
                         doc_path.get().strip(), doc_notes.get().strip() or None)
            else:
                with get_connection() as connection:
                    cur = connection.cursor()
                    cur.execute("""
                        INSERT INTO dbo.ClinicalDocuments
                        (PatientID, DocumentType, FileName, FilePath, DocumentDescription, UploadedAt)
                        VALUES (?, ?, ?, ?, ?, SYSDATETIME())
                    """, patient.PatientID, kind, doc_title.get().strip(),
                         doc_path.get().strip(), doc_notes.get().strip() or None)
            doc_tree.insert("", "end", values=(kind, doc_title.get(), doc_date.get(), doc_path.get(), doc_notes.get()))
            for w in (doc_title, doc_date, doc_path, doc_notes): w.delete(0, tk.END)
            messagebox.showinfo("Saved", "File reference saved to SQL Server.", parent=window)
        except Exception as error:
            messagebox.showerror("Database Error", str(error), parent=window)

    ttk.Button(f, text="Add Document", command=add_document).pack(anchor="e", pady=6)

    # Verify that all seven patient-file pages were created.
    actual_tabs = list(pages.keys())
    if actual_tabs != expected_tabs:
        messagebox.showerror(
            "Patient File Setup Error",
            "The patient file did not initialize all seven sections.\n"
            f"Expected: {expected_tabs}\nActual: {actual_tabs}",
            parent=window
        )
    show_page("Patient Information")

    # Persistent storage for all patient-file tabs.
    # A dedicated table is used so the existing clinical tables are not guessed or modified.
    sections = {
        "Patient Information": {
            "entries": patient_info_entries,
            "trees": []
        },
        "Medical Screening": {
            "entries": {"Blood Pressure": bp, "Pulse": pulse, "Diabetes": diabetes,
                        "Heart Disease": heart, "Bleeding Disorder": blood,
                        "Pregnancy": pregnancy, "Current Medication": medication,
                        "Known Allergies": allergies},
            "texts": {"Additional Screening Notes": screening_notes},
            "trees": []
        },
        "Medical History": {
            "entries": {"Record Type": h_type, "Name / Description": h_name,
                        "Date / Since": h_date, "Status": h_status,
                        "Reaction / Details": h_reaction, "Notes": h_notes},
            "trees": [("history", history_tree)]
        },
        "Dental Chart": {
            "entries": {"Tooth Number": tooth, "Dentition": dentition,
                        "Surface": surface, "Condition": condition, "Notes": tooth_notes},
            "trees": [("dental", dental_tree)]
        },
        "Clinical Visits": {
            "entries": {"Visit Date": visit_date, "Dentist": dentist,
                        "Diagnosis": diagnosis, "Treatment / Procedure": treatment,
                        "Treatment Cost": visit_cost, "Visit Status": visit_status},
            "texts": {"Clinical Notes": visit_notes},
            "trees": [("visits", visit_tree)]
        },
        "Appointments": {
            "entries": {"Appointment Date": ap_date, "Appointment Time": ap_time,
                        "Dentist": ap_dentist, "Reason": ap_reason,
                        "Status": ap_status, "Notes": ap_notes},
            "trees": [("appointments", ap_tree)]
        },
        "Images & Documents": {
            "entries": {"Document Type": doc_type, "Title": doc_title,
                        "Document Date": doc_date, "File Path": doc_path, "Notes": doc_notes},
            "trees": [("documents", doc_tree)]
        }
    }

    def collect_section(section):
        spec = sections[section]
        data = {"entries": {}, "texts": {}, "trees": {}}
        for label, widget in spec.get("entries", {}).items():
            data["entries"][label] = widget.get()
        for label, widget in spec.get("texts", {}).items():
            data["texts"][label] = widget.get("1.0", "end-1c")
        for key, tree in spec.get("trees", []):
            data["trees"][key] = [list(tree.item(item, "values")) for item in tree.get_children()]
        return data

    def apply_section(section, data):
        spec = sections[section]
        for label, value in data.get("entries", {}).items():
            widget = spec.get("entries", {}).get(label)
            if widget is None:
                continue
            if isinstance(widget, ttk.Combobox):
                widget.set(value or "")
            elif str(widget.cget("state")) == "readonly":
                continue
            else:
                widget.delete(0, tk.END)
                widget.insert(0, value or "")
        for label, value in data.get("texts", {}).items():
            widget = spec.get("texts", {}).get(label)
            if widget is not None:
                widget.delete("1.0", tk.END)
                widget.insert("1.0", value or "")
        for key, rows in data.get("trees", {}).items():
            tree = next((t for k, t in spec.get("trees", []) if k == key), None)
            if tree is not None:
                for item in tree.get_children():
                    tree.delete(item)
                for row in rows:
                    tree.insert("", "end", values=row)

    def ensure_patient_medical_screenings_table(cursor):
        cursor.execute("""
            IF OBJECT_ID('dbo.PatientMedicalScreenings', 'U') IS NULL
            BEGIN
                CREATE TABLE dbo.PatientMedicalScreenings (
                    ScreeningID INT IDENTITY(1,1) NOT NULL
                        CONSTRAINT PK_PatientMedicalScreenings PRIMARY KEY,
                    PatientID INT NOT NULL,
                    ScreeningDate DATETIME2 NOT NULL
                        CONSTRAINT DF_PatientMedicalScreenings_ScreeningDate DEFAULT SYSDATETIME(),
                    BloodPressure NVARCHAR(30) NULL,
                    PulseBpm INT NULL,
                    Diabetes NVARCHAR(20) NULL,
                    HeartDisease NVARCHAR(20) NULL,
                    BleedingDisorder NVARCHAR(20) NULL,
                    Pregnancy NVARCHAR(30) NULL,
                    CurrentMedication NVARCHAR(1000) NULL,
                    KnownAllergies NVARCHAR(1000) NULL,
                    AdditionalNotes NVARCHAR(MAX) NULL,
                    CONSTRAINT FK_PatientMedicalScreenings_Patients
                        FOREIGN KEY (PatientID) REFERENCES dbo.Patients(PatientID)
                );
                CREATE INDEX IX_PatientMedicalScreenings_Patient_Date
                    ON dbo.PatientMedicalScreenings(PatientID, ScreeningDate DESC);
            END
        """)

    def ensure_patient_file_table(cursor):
        cursor.execute("""
            IF OBJECT_ID('dbo.PatientFileRecords', 'U') IS NULL
            BEGIN
                CREATE TABLE dbo.PatientFileRecords (
                    RecordID INT IDENTITY(1,1) PRIMARY KEY,
                    PatientID INT NOT NULL,
                    SectionName NVARCHAR(100) NOT NULL,
                    DataJson NVARCHAR(MAX) NOT NULL,
                    CreatedAt DATETIME2 NOT NULL CONSTRAINT DF_PatientFileRecords_CreatedAt DEFAULT SYSUTCDATETIME(),
                    UpdatedAt DATETIME2 NOT NULL CONSTRAINT DF_PatientFileRecords_UpdatedAt DEFAULT SYSUTCDATETIME(),
                    CONSTRAINT FK_PatientFileRecords_Patients
                        FOREIGN KEY (PatientID) REFERENCES dbo.Patients(PatientID),
                    CONSTRAINT UQ_PatientFileRecords_Patient_Section UNIQUE (PatientID, SectionName)
                );
            END
        """)

    def save_medical_screening(show_message=True):
        try:
            pulse_value = pulse.get().strip()
            if pulse_value and not pulse_value.isdigit():
                messagebox.showwarning("Invalid Pulse", "Pulse must be a whole number.", parent=window)
                return False
            pulse_db = int(pulse_value) if pulse_value else None

            with get_connection() as connection:
                cursor = connection.cursor()
                ensure_patient_medical_screenings_table(cursor)
                cursor.execute("""
                    INSERT INTO dbo.PatientMedicalScreenings
                    (PatientID, ScreeningDate, BloodPressure, PulseBpm, Diabetes, HeartDisease,
                     BleedingDisorder, Pregnancy, CurrentMedication, KnownAllergies,
                     AdditionalNotes)
                    VALUES (?, SYSDATETIME(), ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    patient.PatientID,
                    bp.get().strip() or None,
                    pulse_db,
                    diabetes.get().strip() or None,
                    heart.get().strip() or None,
                    blood.get().strip() or None,
                    pregnancy.get().strip() or None,
                    medication.get().strip() or None,
                    allergies.get().strip() or None,
                    screening_notes.get("1.0", "end-1c").strip() or None
                )
            if show_message:
                messagebox.showinfo("Saved", "Medical Screening saved to dbo.PatientMedicalScreenings.", parent=window)
            return True
        except Exception as error:
            messagebox.showerror("Save Error", f"Could not save Medical Screening:\\n{error}", parent=window)
            return False

    def load_latest_medical_screening():
        try:
            with get_connection() as connection:
                cursor = connection.cursor()
                ensure_patient_medical_screenings_table(cursor)
                cursor.execute("""
                    SELECT TOP (1) BloodPressure, PulseBpm, Diabetes, HeartDisease,
                           BleedingDisorder, Pregnancy, CurrentMedication, KnownAllergies,
                           AdditionalNotes
                    FROM dbo.PatientMedicalScreenings
                    WHERE PatientID = ?
                    ORDER BY ScreeningDate DESC, ScreeningID DESC
                """, patient.PatientID)
                row = cursor.fetchone()
            if row:
                bp.delete(0, tk.END); bp.insert(0, row.BloodPressure or "")
                pulse.delete(0, tk.END); pulse.insert(0, "" if row.PulseBpm is None else str(row.PulseBpm))
                diabetes.set(row.Diabetes or "")
                heart.set(row.HeartDisease or "")
                blood.set(row.BleedingDisorder or "")
                pregnancy.set(row.Pregnancy or "")
                medication.delete(0, tk.END); medication.insert(0, row.CurrentMedication or "")
                allergies.delete(0, tk.END); allergies.insert(0, row.KnownAllergies or "")
                screening_notes.delete("1.0", tk.END)
                screening_notes.insert("1.0", row.AdditionalNotes or "")
        except Exception as error:
            messagebox.showerror("Load Error", f"Could not load Medical Screening:\\n{error}", parent=window)

    def save_section(section, show_message=True):
        if section == "Medical Screening":
            return save_medical_screening(show_message)
        if section == "Patient Information":
            try:
                with get_connection() as connection:
                    cursor = connection.cursor()
                    cursor.execute("""
                        UPDATE dbo.Patients
                        SET FirstName=?, LastName=?, NationalCode=?, MobileNumber=?,
                            LastModifiedAt=SYSDATETIME()
                        WHERE PatientID=?
                    """,
                        patient_info_entries["First Name"].get().strip(),
                        patient_info_entries["Last Name"].get().strip(),
                        patient_info_entries["National Code"].get().strip() or None,
                        patient_info_entries["Mobile Number"].get().strip() or None,
                        patient.PatientID
                    )
                    cursor.connection.commit()
                if show_message: messagebox.showinfo("Saved", "Patient information updated.", parent=window)
                refresh_patient_information(show_message=False)
                return True
            except Exception as error:
                messagebox.showerror("Save Error", str(error), parent=window); return False
        try:
            payload = json.dumps(collect_section(section), ensure_ascii=False)
            with get_connection() as connection:
                cursor = connection.cursor()
                ensure_patient_file_table(cursor)
                cursor.execute("""
                    UPDATE dbo.PatientFileRecords
                    SET DataJson = ?, UpdatedAt = SYSUTCDATETIME()
                    WHERE PatientID = ? AND SectionName = ?
                """, payload, patient.PatientID, section)
                if cursor.rowcount == 0:
                    cursor.execute("""
                        INSERT INTO dbo.PatientFileRecords (PatientID, SectionName, DataJson)
                        VALUES (?, ?, ?)
                    """, patient.PatientID, section, payload)
            if show_message:
                messagebox.showinfo("Saved", f"{section} saved successfully.", parent=window)
            return True
        except Exception as error:
            messagebox.showerror("Save Error", f"Could not save {section}:\\n{error}", parent=window)
            return False

    def load_saved_sections():
        try:
            with get_connection() as connection:
                cursor = connection.cursor()
                ensure_patient_file_table(cursor)
                cursor.execute("""
                    SELECT SectionName, DataJson
                    FROM dbo.PatientFileRecords
                    WHERE PatientID = ?
                """, patient.PatientID)
                rows = cursor.fetchall()
            for row in rows:
                # Patient demographics must ALWAYS come from dbo.Patients.
                # Older versions also stored a JSON copy in PatientFileRecords;
                # loading that stale copy overwrote the current database values.
                if row.SectionName == "Patient Information":
                    continue
                if row.SectionName in sections:
                    try:
                        apply_section(row.SectionName, json.loads(row.DataJson))
                    except (ValueError, TypeError, json.JSONDecodeError):
                        continue

            # Re-read demographics last so the visible header and fields are
            # guaranteed to reflect the current dbo.Patients row.
            refresh_patient_information(show_message=False)
        except Exception as error:
            messagebox.showerror("Load Error", f"Could not load saved patient-file data:\\n{error}", parent=window)

    def save_all_sections():
        saved = 0
        for section_name in sections:
            if save_section(section_name, show_message=False):
                saved += 1
            else:
                return
        messagebox.showinfo("Saved", f"All {saved} patient-file sections saved successfully.", parent=window)

    load_saved_sections()
    load_latest_medical_screening()

    def load_relational_records():
        """Populate patient-file grids from the clinic's existing relational tables."""
        try:
            with get_connection() as connection:
                cur = connection.cursor()

                # Medical history and allergies
                cur.execute("""
                    SELECT MedicalNoteType, MedicalNoteText, CreatedAt
                    FROM dbo.PatientMedicalNotes WHERE PatientID=?
                    ORDER BY CreatedAt DESC
                """, patient.PatientID)
                for r in cur.fetchall():
                    history_tree.insert("", "end", values=(r.MedicalNoteType or "Medical Condition",
                        (r.MedicalNoteText or "")[:180], r.CreatedAt, "", "", ""))
                cur.execute("""
                    SELECT AllergenName, AllergicReaction, SeverityLevel, AllergyNotes, CreatedAt
                    FROM dbo.PatientAllergies WHERE PatientID=? ORDER BY CreatedAt DESC
                """, patient.PatientID)
                for r in cur.fetchall():
                    history_tree.insert("", "end", values=("Allergy", r.AllergenName, r.CreatedAt,
                        r.SeverityLevel or "", r.AllergicReaction or "", r.AllergyNotes or ""))

                # Tooth clinical history
                cur.execute("""
                    SELECT t.ToothCode, t.IsPermanent, s.SurfaceName,
                           COALESCE(ct.ConditionName, tr.ClinicalCondition),
                           tr.ClinicalDescription
                    FROM dbo.ToothClinicalRecords tr
                    INNER JOIN dbo.ClinicalVisits v ON v.ClinicalVisitID=tr.ClinicalVisitID
                    INNER JOIN dbo.Teeth t ON t.ToothID=tr.ToothID
                    LEFT JOIN dbo.ToothSurfaces s ON s.ToothSurfaceID=tr.ToothSurfaceID
                    LEFT JOIN dbo.ToothConditionTypes ct ON ct.ToothConditionTypeID=tr.ToothConditionTypeID
                    WHERE v.PatientID=? ORDER BY tr.RecordedAt DESC
                """, patient.PatientID)
                for r in cur.fetchall():
                    dental_tree.insert("", "end", values=(r.ToothCode,
                        "Permanent" if r.IsPermanent else "Primary", r.SurfaceName or "None",
                        r[3] or "", r.ClinicalDescription or ""))

                # Clinical visits
                cur.execute("""
                    SELECT v.VisitDateTime, d.FirstName + N' ' + d.LastName,
                           v.Diagnosis, v.ClinicalNotes
                    FROM dbo.ClinicalVisits v
                    INNER JOIN dbo.Dentists d ON d.DentistID=v.DentistID
                    WHERE v.PatientID=? ORDER BY v.VisitDateTime DESC
                """, patient.PatientID)
                for r in cur.fetchall():
                    visit_tree.insert("", "end", values=(r.VisitDateTime, r[1],
                        r.Diagnosis or "", "", "", r.ClinicalNotes or ""))

                # Appointments
                cur.execute("""
                    SELECT a.AppointmentStartDateTime, d.FirstName + N' ' + d.LastName,
                           a.AppointmentReason, st.StatusName, a.AppointmentNotes
                    FROM dbo.Appointments a
                    INNER JOIN dbo.Dentists d ON d.DentistID=a.DentistID
                    INNER JOIN dbo.AppointmentStatuses st ON st.AppointmentStatusID=a.AppointmentStatusID
                    WHERE a.PatientID=? ORDER BY a.AppointmentStartDateTime DESC
                """, patient.PatientID)
                for r in cur.fetchall():
                    ap_tree.insert("", "end", values=(r.AppointmentStartDateTime,
                        "", r[1], r.AppointmentReason or "", r.StatusName, r.AppointmentNotes or ""))

                # Images and documents
                cur.execute("""
                    SELECT ImageType, FileName, UploadedAt, FilePath, ImageDescription
                    FROM dbo.DentalImages WHERE PatientID=?
                    UNION ALL
                    SELECT DocumentType, FileName, UploadedAt, FilePath, DocumentDescription
                    FROM dbo.ClinicalDocuments WHERE PatientID=?
                    ORDER BY 3 DESC
                """, patient.PatientID, patient.PatientID)
                for r in cur.fetchall():
                    doc_tree.insert("", "end", values=tuple("" if x is None else x for x in r))
        except Exception as error:
            messagebox.showerror("Load Error", f"Could not load existing patient records:\\n{error}", parent=window)

    load_relational_records()

    def refresh_all_patient_sections(show_errors=True):
        """Silently reload every patient-file section from SQL Server."""
        try:
            # Patient demographics may have been edited in Patient Management.
            refresh_patient_information(show_message=False)

            # Reload the latest medical screening values.
            load_latest_medical_screening()

            # Clear all record grids before repopulating them to avoid duplicates.
            for tree in (history_tree, dental_tree, visit_tree, ap_tree, doc_tree):
                for item in tree.get_children():
                    tree.delete(item)

            # Reload saved form sections and relational records for this patient.
            load_saved_sections()
            load_relational_records()
            return True
        except Exception as error:
            if show_errors:
                messagebox.showerror(
                    "Automatic Update Error",
                    f"Could not refresh all patient-file sections:\n{error}",
                    parent=window
                )
            return False

    # Refresh automatically when the patient-file window becomes active again,
    # e.g. after editing the patient in Patient Management.
    def on_patient_file_focus(event):
        # Only refresh when the top-level window itself regains focus, not
        # while the user is moving between fields inside the form.
        if event.widget is window:
            window.after_idle(lambda: refresh_all_patient_sections(show_errors=False))

    window.bind("<FocusIn>", on_patient_file_focus)

    # Persistent action bar at the bottom, visible regardless of the selected section.
    toolbar = tk.Frame(window, bg="#E8EDF2", padx=12, pady=8, bd=1, relief="solid")
    toolbar.pack(side="bottom", fill="x", padx=12, pady=(0, 10), before=page_container)
    current_save_button = tk.Button(
        toolbar, text="Save Patient Information",
        command=lambda: save_section(active_page["name"]),
        bg="#1976D2", fg="white", activebackground="#125A9C",
        font=("Arial", 10, "bold"), padx=14, pady=7, cursor="hand2"
    )
    current_save_button.pack(side="left")
    tk.Button(
        toolbar, text="Save All Sections", command=save_all_sections,
        bg="#198754", fg="white", activebackground="#146C43",
        font=("Arial", 10, "bold"), padx=14, pady=7, cursor="hand2"
    ).pack(side="left", padx=8)
    tk.Label(toolbar, text="Changes are saved to this patient's file.",
             bg="#E8EDF2", fg="#526579",
             font=("Arial", 9)).pack(side="left", padx=12)
    tk.Button(toolbar, text="Close", command=window.destroy,
              padx=16, pady=6).pack(side="right")

    _original_show_page = show_page
    def show_page_with_save_label(title):
        _original_show_page(title)
        current_save_button.config(text=f"Save {{title}}")
    show_page = show_page_with_save_label
    show_page("Patient Information")


def show_patients():
    window = tk.Toplevel(root)
    window.title("Patient Management")
    window.geometry("1000x600")
    window.minsize(850, 500)

    tk.Label(window, text="Patient List", font=("Arial", 16, "bold")).pack(pady=10)
    search_frame = tk.Frame(window)
    search_frame.pack(pady=10)
    tk.Label(search_frame, text="Search:").pack(side="left")
    search_entry = tk.Entry(search_frame, width=35)
    search_entry.pack(side="left", padx=10)

    columns = ("ID", "FirstName", "LastName", "NationalCode", "Mobile")
    table_frame = tk.Frame(window)
    table_frame.pack(fill="both", expand=True, padx=15, pady=10)
    table = ttk.Treeview(table_frame, columns=columns, show="headings", height=14)
    headers = {
        "ID": ("Patient ID", 85), "FirstName": ("First Name", 180),
        "LastName": ("Last Name", 180), "NationalCode": ("National Code", 180),
        "Mobile": ("Mobile Number", 180)
    }
    for col in columns:
        title, width = headers[col]
        table.heading(col, text=title)
        table.column(col, width=width, anchor="center")
    scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=table.yview)
    table.configure(yscrollcommand=scrollbar.set)
    table.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    def load_patients():
        table.delete(*table.get_children())
        search = f"%{search_entry.get().strip()}%"
        try:
            with get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute("""
                    SELECT PatientID, FirstName, LastName, NationalCode, MobileNumber
                    FROM dbo.Patients
                    WHERE FirstName LIKE ? OR LastName LIKE ?
                       OR NationalCode LIKE ? OR MobileNumber LIKE ?
                    ORDER BY PatientID DESC
                """, search, search, search, search)
                for patient in cursor.fetchall():
                    table.insert("", "end", values=tuple(
                        "" if value is None else value for value in patient
                    ))
        except pyodbc.Error as error:
            messagebox.showerror("Database Error", str(error), parent=window)

    def edit_selected_patient():
        selected = table.selection()
        if not selected:
            messagebox.showwarning("Select Patient", "Please select a patient first.", parent=window)
            return
        values = table.item(selected[0], "values")
        patient_id = int(values[0])

        edit_window = tk.Toplevel(window)
        edit_window.title("Edit Patient")
        edit_window.geometry("430x330")
        edit_window.resizable(False, False)
        edit_window.transient(window)
        edit_window.grab_set()

        tk.Label(edit_window, text=f"Edit Patient (ID: {patient_id})",
                 font=("Arial", 14, "bold")).pack(pady=15)
        fields = [
            ("First Name", values[1]), ("Last Name", values[2]),
            ("National Code", values[3]), ("Mobile Number", values[4])
        ]
        entries = {}
        form = tk.Frame(edit_window)
        form.pack(padx=25, pady=5)
        for row, (label, value) in enumerate(fields):
            tk.Label(form, text=label, width=16, anchor="w").grid(
                row=row, column=0, padx=6, pady=8, sticky="w")
            entry = tk.Entry(form, width=27)
            entry.grid(row=row, column=1, padx=6, pady=8)
            entry.insert(0, value)
            entries[label] = entry

        def save_changes():
            first = entries["First Name"].get().strip()
            last = entries["Last Name"].get().strip()
            national = entries["National Code"].get().strip()
            mobile = entries["Mobile Number"].get().strip()
            if not first or not last:
                messagebox.showwarning("Validation", "First name and last name are required.",
                                       parent=edit_window)
                return
            try:
                with get_connection() as connection:
                    cursor = connection.cursor()
                    cursor.execute("""
                        UPDATE dbo.Patients
                        SET FirstName = ?, LastName = ?, NationalCode = ?, MobileNumber = ?
                        WHERE PatientID = ?
                    """, first, last, national, mobile, patient_id)
                    if cursor.rowcount == 0:
                        raise RuntimeError("The selected patient was not found.")
                    connection.commit()
                messagebox.showinfo("Updated", "Patient information updated successfully.",
                                    parent=edit_window)
                edit_window.destroy()
                load_patients()
            except (pyodbc.Error, RuntimeError) as error:
                messagebox.showerror("Update Error", str(error), parent=edit_window)

        tk.Button(edit_window, text="Save Changes", command=save_changes,
                  bg="#1976D2", fg="white", font=("Arial", 10, "bold"),
                  width=20).pack(pady=15)

    tk.Button(search_frame, text="Search", command=load_patients).pack(side="left")
    search_entry.bind("<Return>", lambda event: load_patients())
    action_frame = tk.Frame(window)
    action_frame.pack(fill="x", padx=15, pady=(0, 12))
    tk.Button(action_frame, text="Edit Selected Patient", command=edit_selected_patient,
              bg="#1976D2", fg="white", font=("Arial", 10, "bold"),
              width=22).pack(side="left", padx=5)

    def delete_selected_patient():
        selected = table.selection()
        if not selected:
            messagebox.showwarning(
                "Select Patient", "Please select a patient first.", parent=window
            )
            return

        values = table.item(selected[0], "values")
        patient_id = int(values[0])
        patient_name = f"{values[1]} {values[2]}".strip()

        # Always ask for confirmation before attempting deletion.
        if not messagebox.askyesno(
            "Confirm Patient Deletion",
            f"Are you sure you want to delete patient {patient_name} (ID: {patient_id})?\n\n"
            "This action cannot be undone.",
            icon="warning", parent=window
        ):
            return

        try:
            with get_connection() as connection:
                cursor = connection.cursor()

                # Find every table that either has a PatientID column or has a
                # foreign key pointing directly to dbo.Patients. If any such
                # record exists, keep the patient and explain why deletion is blocked.
                cursor.execute("""
                    SELECT DISTINCT s.name AS SchemaName, t.name AS TableName,
                           c.name AS PatientColumn
                    FROM sys.tables AS t
                    INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
                    INNER JOIN sys.columns AS c ON c.object_id = t.object_id
                    WHERE t.object_id <> OBJECT_ID(N'dbo.Patients')
                      AND c.name = N'PatientID'
                    UNION
                    SELECT DISTINCT ps.name, pt.name, pc.name
                    FROM sys.foreign_keys AS fk
                    INNER JOIN sys.tables AS pt ON pt.object_id = fk.parent_object_id
                    INNER JOIN sys.schemas AS ps ON ps.schema_id = pt.schema_id
                    INNER JOIN sys.foreign_key_columns AS fkc
                        ON fkc.constraint_object_id = fk.object_id
                    INNER JOIN sys.columns AS pc
                        ON pc.object_id = fkc.parent_object_id
                       AND pc.column_id = fkc.parent_column_id
                    WHERE fk.referenced_object_id = OBJECT_ID(N'dbo.Patients')
                """)
                related_tables = cursor.fetchall()
                linked_records = []
                checked = set()
                for schema_name, table_name, patient_column in related_tables:
                    key = (schema_name, table_name, patient_column)
                    if key in checked:
                        continue
                    checked.add(key)
                    sql = (
                        f"SELECT COUNT_BIG(1) FROM [{schema_name.replace(']', ']]')}]"
                        f".[{table_name.replace(']', ']]')}] "
                        f"WHERE [{patient_column.replace(']', ']]')}] = ?"
                    )
                    cursor.execute(sql, patient_id)
                    count = cursor.fetchone()[0]
                    if count:
                        linked_records.append((table_name, int(count)))

                if linked_records:
                    details = "\n".join(
                        f"• {table_name}: {count} record(s)"
                        for table_name, count in linked_records
                    )
                    messagebox.showwarning(
                        "Patient Cannot Be Deleted",
                        f"Patient {patient_name} (ID: {patient_id}) has an existing patient file or related records.\n\n"
                        "For data integrity, this patient cannot be deleted.\n\n"
                        f"Related records found:\n{details}",
                        parent=window
                    )
                    return

                cursor.execute(
                    "DELETE FROM dbo.Patients WHERE PatientID = ?", patient_id
                )
                if cursor.rowcount == 0:
                    connection.rollback()
                    messagebox.showwarning(
                        "Patient Not Found", "The selected patient no longer exists.",
                        parent=window
                    )
                    load_patients()
                    return
                connection.commit()

            messagebox.showinfo(
                "Patient Deleted", "The patient was deleted successfully.", parent=window
            )
            load_patients()
        except (pyodbc.Error, RuntimeError) as error:
            messagebox.showerror(
                "Delete Error",
                "The patient could not be deleted. No deletion was completed.\n\n"
                f"Database details: {error}",
                parent=window
            )

    tk.Button(action_frame, text="Delete Selected Patient", command=delete_selected_patient,
              bg="#C62828", fg="white", font=("Arial", 10, "bold"),
              width=22).pack(side="left", padx=5)

    def open_selected_patient_file():
        selected = table.selection()
        if not selected:
            messagebox.showwarning("Select Patient", "Please select a patient first.", parent=window)
            return
        patient_id = int(table.item(selected[0], "values")[0])
        show_patient_file(patient_id)

    tk.Button(action_frame, text="Patient File", command=open_selected_patient_file,
              bg="#0D6E8A", fg="white", font=("Arial", 10, "bold"),
              width=16).pack(side="left", padx=5)
    tk.Button(action_frame, text="Refresh", command=load_patients,
              width=12).pack(side="left", padx=5)
    table.bind("<Double-1>", lambda event: edit_selected_patient())
    load_patients()


def show_dentists():
    window = tk.Toplevel(root)
    window.title("Dentist Management")
    window.geometry("1050x600")

    tk.Label(window, text="Dentist Management",
             font=("Arial", 17, "bold")).pack(pady=12)

    search_frame = tk.Frame(window)
    search_frame.pack(fill="x", padx=15, pady=5)
    tk.Label(search_frame, text="Search:").pack(side="left")
    search_entry = tk.Entry(search_frame, width=35)
    search_entry.pack(side="left", padx=8)

    columns = ("ID", "License", "FirstName", "LastName",
               "Mobile", "Email", "Specialization", "Active")
    table_frame = tk.Frame(window)
    table_frame.pack(fill="both", expand=True, padx=15, pady=10)

    table = ttk.Treeview(table_frame, columns=columns, show="headings", height=14)
    headings = {
        "ID": ("ID", 55),
        "License": ("Dental License No.", 130),
        "FirstName": ("First Name", 110),
        "LastName": ("Last Name", 120),
        "Mobile": ("Mobile", 110),
        "Email": ("Email", 180),
        "Specialization": ("Specialization", 150),
        "Active": ("Active", 70)
    }
    for col in columns:
        title, width = headings[col]
        table.heading(col, text=title)
        table.column(col, width=width, minwidth=55, anchor="center")

    yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=table.yview)
    xscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=table.xview)
    table.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
    table.grid(row=0, column=0, sticky="nsew")
    yscroll.grid(row=0, column=1, sticky="ns")
    xscroll.grid(row=1, column=0, sticky="ew")
    table_frame.rowconfigure(0, weight=1)
    table_frame.columnconfigure(0, weight=1)

    def load_dentists():
        table.delete(*table.get_children())
        search = f"%{search_entry.get().strip()}%"
        try:
            with get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute("""
                    SELECT DentistID, DentalLicenseNumber, FirstName, LastName,
                           MobileNumber, EmailAddress, Specialization, IsActive
                    FROM dbo.Dentists
                    WHERE COALESCE(DentalLicenseNumber, '') LIKE ?
                       OR FirstName LIKE ? OR LastName LIKE ?
                       OR COALESCE(MobileNumber, '') LIKE ?
                       OR COALESCE(EmailAddress, '') LIKE ?
                       OR COALESCE(Specialization, '') LIKE ?
                    ORDER BY DentistID DESC
                """, search, search, search, search, search, search)
                for row in cursor.fetchall():
                    values = list(row)
                    values[-1] = "Yes" if values[-1] else "No"
                    table.insert("", "end", iid=str(row[0]), values=values)
        except pyodbc.Error as error:
            messagebox.showerror("Database Error", str(error))

    def dentist_form(dentist_id=None):
        form = tk.Toplevel(window)
        form.title("Edit Dentist" if dentist_id else "Add Dentist")
        form.geometry("430x430")
        form.resizable(False, False)

        current = None
        if dentist_id is not None:
            try:
                with get_connection() as connection:
                    cursor = connection.cursor()
                    cursor.execute("""
                        SELECT DentalLicenseNumber, FirstName, LastName,
                               MobileNumber, EmailAddress, Specialization, IsActive
                        FROM dbo.Dentists WHERE DentistID = ?
                    """, dentist_id)
                    current = cursor.fetchone()
                if current is None:
                    messagebox.showerror("Not found", "Dentist record was not found.")
                    form.destroy()
                    return
            except pyodbc.Error as error:
                messagebox.showerror("Database Error", str(error))
                form.destroy()
                return

        fields = [
            ("Dental License Number", "license"),
            ("First Name", "first"),
            ("Last Name", "last"),
            ("Mobile Number", "mobile"),
            ("Email Address", "email"),
            ("Specialization", "specialization")
        ]
        entries = {}
        for label_text, key in fields:
            row = tk.Frame(form)
            row.pack(fill="x", padx=20, pady=7)
            tk.Label(row, text=label_text, width=20, anchor="w").pack(side="left")
            entry = tk.Entry(row, width=28)
            entry.pack(side="right")
            entries[key] = entry

        active_var = tk.BooleanVar(value=True if current is None else bool(current[6]))
        tk.Checkbutton(form, text="Active dentist", variable=active_var).pack(pady=8)

        if current is not None:
            for (label_text, key), value in zip(fields, current[:6]):
                entries[key].insert(0, "" if value is None else str(value))

        def save_dentist():
            license_no = entries["license"].get().strip()
            first = entries["first"].get().strip()
            last = entries["last"].get().strip()
            mobile = entries["mobile"].get().strip()
            email = entries["email"].get().strip()
            specialization = entries["specialization"].get().strip()

            if not first or not last:
                messagebox.showwarning("Validation", "First name and last name are required.", parent=form)
                return

            try:
                with get_connection() as connection:
                    cursor = connection.cursor()
                    if dentist_id is None:
                        cursor.execute("""
                            INSERT INTO dbo.Dentists
                                (DentalLicenseNumber, FirstName, LastName,
                                 MobileNumber, EmailAddress, Specialization, IsActive)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, license_no or None, first, last, mobile or None,
                             email or None, specialization or None, active_var.get())
                    else:
                        cursor.execute("""
                            UPDATE dbo.Dentists
                            SET DentalLicenseNumber = ?, FirstName = ?, LastName = ?,
                                MobileNumber = ?, EmailAddress = ?, Specialization = ?,
                                IsActive = ?
                            WHERE DentistID = ?
                        """, license_no or None, first, last, mobile or None,
                             email or None, specialization or None,
                             active_var.get(), dentist_id)

                messagebox.showinfo("Success", "Dentist saved successfully.", parent=form)
                form.destroy()
                load_dentists()
            except pyodbc.Error as error:
                messagebox.showerror("Database Error", str(error), parent=form)

        tk.Button(form, text="Save", command=save_dentist,
                  bg="#1976D2", fg="white", width=18).pack(pady=15)

    def add_dentist():
        dentist_form()

    def edit_dentist():
        selected = table.selection()
        if not selected:
            messagebox.showwarning("Select Dentist", "Please select a dentist first.", parent=window)
            return
        dentist_form(int(selected[0]))

    def delete_dentist():
        selected = table.selection()
        if not selected:
            messagebox.showwarning("Select Dentist", "Please select a dentist first.", parent=window)
            return
        dentist_id = int(selected[0])
        if not messagebox.askyesno("Confirm Delete",
                                   "Are you sure you want to delete this dentist?",
                                   parent=window):
            return
        try:
            with get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute("DELETE FROM dbo.Dentists WHERE DentistID = ?", dentist_id)
            load_dentists()
            messagebox.showinfo("Deleted", "Dentist deleted successfully.", parent=window)
        except pyodbc.IntegrityError:
            messagebox.showerror(
                "Cannot Delete",
                "This dentist is linked to other records. Deactivate the dentist instead.",
                parent=window
            )
        except pyodbc.Error as error:
            messagebox.showerror("Database Error", str(error), parent=window)

    tk.Button(search_frame, text="Search", command=load_dentists).pack(side="left", padx=3)
    search_entry.bind("<Return>", lambda event: load_dentists())

    buttons = tk.Frame(window)
    buttons.pack(pady=8)
    tk.Button(buttons, text="Add Dentist", command=add_dentist,
              bg="#198754", fg="white", width=15).pack(side="left", padx=5)
    tk.Button(buttons, text="Edit Selected", command=edit_dentist,
              bg="#1976D2", fg="white", width=15).pack(side="left", padx=5)
    tk.Button(buttons, text="Delete Selected", command=delete_dentist,
              bg="#C62828", fg="white", width=15).pack(side="left", padx=5)
    tk.Button(buttons, text="Refresh", command=load_dentists,
              width=12).pack(side="left", padx=5)

    load_dentists()







def manage_dentist_working_hours():
    """Configure weekly working days and hours for each dentist."""
    window = tk.Toplevel(root)
    window.title("Dentist Working Hours")
    window.geometry("760x570")
    window.resizable(False, False)

    tk.Label(
        window, text="Dentist Weekly Working Schedule",
        font=("Arial", 16, "bold")
    ).pack(pady=12)

    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute("""
                SELECT DentistID, FirstName, LastName
                FROM dbo.Dentists
                WHERE IsActive = 1
                ORDER BY FirstName, LastName
            """)
            dentists = cursor.fetchall()
    except pyodbc.Error as error:
        messagebox.showerror("Database Error", str(error), parent=window)
        window.destroy()
        return

    if not dentists:
        messagebox.showwarning("No Dentists", "Register an active dentist first.", parent=window)
        window.destroy()
        return

    dentist_map = {
        f"Dr. {r.FirstName} {r.LastName} (ID: {r.DentistID})": r.DentistID
        for r in dentists
    }

    top = tk.Frame(window)
    top.pack(fill="x", padx=25, pady=8)
    tk.Label(top, text="Dentist:").pack(side="left", padx=5)
    dentist_var = tk.StringVar()
    dentist_combo = ttk.Combobox(
        top, textvariable=dentist_var, values=list(dentist_map),
        state="readonly", width=38
    )
    dentist_combo.pack(side="left", padx=5)
    dentist_combo.current(0)

    days = [
        ("Monday", 0), ("Tuesday", 1), ("Wednesday", 2),
        ("Thursday", 3), ("Friday", 4), ("Saturday", 5),
        ("Sunday", 6)
    ]

    grid = tk.Frame(window)
    grid.pack(padx=25, pady=12)
    headers = ["Working Day", "Working?", "Start Time", "End Time"]
    for col, heading in enumerate(headers):
        tk.Label(grid, text=heading, font=("Arial", 10, "bold")).grid(
            row=0, column=col, padx=12, pady=7
        )

    day_controls = {}
    for row, (day_name, day_no) in enumerate(days, start=1):
        tk.Label(grid, text=day_name, width=15, anchor="w").grid(
            row=row, column=0, padx=8, pady=7
        )
        enabled = tk.BooleanVar(value=(day_no < 5))
        check = tk.Checkbutton(grid, variable=enabled)
        check.grid(row=row, column=1, padx=10)
        start_var = tk.StringVar(value="09:00")
        end_var = tk.StringVar(value="17:00")
        start_box = ttk.Entry(grid, textvariable=start_var, width=12)
        end_box = ttk.Entry(grid, textvariable=end_var, width=12)
        start_box.grid(row=row, column=2, padx=8, pady=7)
        end_box.grid(row=row, column=3, padx=8, pady=7)
        day_controls[day_no] = (enabled, start_var, end_var)

    tk.Label(
        window,
        text="Time format: HH:MM (24-hour). Uncheck days when the dentist is not working.",
        fg="#555555"
    ).pack(pady=8)

    def load_schedule(*args):
        dentist_id = dentist_map.get(dentist_var.get())
        if not dentist_id:
            return
        try:
            with get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute("""
                    SELECT DayOfWeek, IsActive, WorkStartTime, WorkEndTime
                    FROM dbo.DentistWorkingHours
                    WHERE DentistID = ?
                """, dentist_id)
                saved = {r.DayOfWeek - 1: r for r in cursor.fetchall()}

            for day_no, (enabled, start_var, end_var) in day_controls.items():
                if day_no in saved:
                    r = saved[day_no]
                    enabled.set(bool(r.IsActive))
                    start_var.set(r.WorkStartTime.strftime("%H:%M") if r.WorkStartTime else "09:00")
                    end_var.set(r.WorkEndTime.strftime("%H:%M") if r.WorkEndTime else "17:00")
                else:
                    enabled.set(False)
                    start_var.set("09:00")
                    end_var.set("17:00")
        except pyodbc.Error as error:
            messagebox.showerror("Database Error", str(error), parent=window)

    def save_schedule():
        from datetime import datetime
        dentist_id = dentist_map.get(dentist_var.get())
        if not dentist_id:
            return

        records = []
        try:
            for day_no, (enabled, start_var, end_var) in day_controls.items():
                if enabled.get():
                    start_time = datetime.strptime(start_var.get().strip(), "%H:%M").time()
                    end_time = datetime.strptime(end_var.get().strip(), "%H:%M").time()
                    if end_time <= start_time:
                        raise ValueError(f"End time must be later than start time ({days[day_no][0]}).")
                    records.append((day_no, True, start_time, end_time))
                else:
                    # The existing SQL table defines WorkStartTime and
                    # WorkEndTime as NOT NULL, even for inactive days.
                    # Keep valid time values while marking the day inactive.
                    start_time = datetime.strptime(start_var.get().strip(), "%H:%M").time()
                    end_time = datetime.strptime(end_var.get().strip(), "%H:%M").time()
                    if end_time <= start_time:
                        raise ValueError(
                            f"End time must be later than start time ({days[day_no][0]})."
                        )
                    records.append((day_no, False, start_time, end_time))
        except ValueError as error:
            messagebox.showwarning(
                "Invalid Schedule", f"Check the time values. {error}", parent=window
            )
            return

        try:
            with get_connection() as connection:
                cursor = connection.cursor()
                for day_no, is_working, start_time, end_time in records:
                    cursor.execute("""
                        IF EXISTS
                        (
                            SELECT 1 FROM dbo.DentistWorkingHours
                            WHERE DentistID = ? AND DayOfWeek = ?
                        )
                            UPDATE dbo.DentistWorkingHours
                            SET IsActive = ?, WorkStartTime = ?, WorkEndTime = ?
                            WHERE DentistID = ? AND DayOfWeek = ?;
                        ELSE
                            INSERT INTO dbo.DentistWorkingHours
                                (DentistID, DayOfWeek, IsActive, WorkStartTime, WorkEndTime)
                            VALUES (?, ?, ?, ?, ?);
                    """,
                        dentist_id, day_no + 1,
                        is_working, start_time, end_time, dentist_id, day_no + 1,
                        dentist_id, day_no + 1, is_working, start_time, end_time
                    )
                connection.commit()
            messagebox.showinfo(
                "Saved", "Dentist working hours saved successfully.", parent=window
            )
        except pyodbc.Error as error:
            messagebox.showerror("Database Error", str(error), parent=window)

    dentist_combo.bind("<<ComboboxSelected>>", load_schedule)
    tk.Button(
        window, text="Save Working Hours", command=save_schedule,
        bg="#198754", fg="white", width=22
    ).pack(pady=14)
    load_schedule()


def create_appointment(on_saved=None):
    """Book a patient into the next available slot for the selected dentist."""
    from datetime import datetime, timedelta

    form = tk.Toplevel(root)
    form.title("Book an Appointment")
    form.geometry("570x650")
    form.resizable(False, False)

    tk.Label(form, text="New Appointment",
             font=("Arial", 16, "bold")).pack(pady=14)

    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute("""
                SELECT PatientID, FirstName, LastName
                FROM dbo.Patients ORDER BY FirstName, LastName
            """)
            patients = cursor.fetchall()
            cursor.execute("""
                SELECT DentistID, FirstName, LastName
                FROM dbo.Dentists WHERE IsActive = 1
                ORDER BY FirstName, LastName
            """)
            dentists = cursor.fetchall()
            cursor.execute("""
                SELECT AppointmentStatusID, StatusName
                FROM dbo.AppointmentStatuses ORDER BY AppointmentStatusID
            """)
            statuses = cursor.fetchall()
    except pyodbc.Error as error:
        messagebox.showerror("Database Error", str(error), parent=form)
        form.destroy()
        return

    if not patients or not dentists or not statuses:
        messagebox.showwarning(
            "Missing data",
            "Make sure patients, active dentists, and appointment statuses exist.",
            parent=form
        )
        form.destroy()
        return

    patient_map = {
        f"{r.FirstName} {r.LastName} (ID: {r.PatientID})": r.PatientID
        for r in patients
    }
    dentist_map = {
        f"Dr. {r.FirstName} {r.LastName} (ID: {r.DentistID})": r.DentistID
        for r in dentists
    }
    status_map = {r.StatusName: r.AppointmentStatusID for r in statuses}

    body = tk.Frame(form)
    body.pack(fill="both", expand=True, padx=28, pady=5)
    body.columnconfigure(1, weight=1)

    def add_label(text, row):
        tk.Label(body, text=text, width=18, anchor="w").grid(
            row=row, column=0, padx=5, pady=8, sticky="w"
        )

    add_label("Patient:", 0)
    patient_var = tk.StringVar()
    patient_combo = ttk.Combobox(
        body, textvariable=patient_var, values=list(patient_map),
        state="readonly", width=36
    )
    patient_combo.grid(row=0, column=1, padx=5, pady=8, sticky="ew")
    patient_combo.current(0)

    add_label("Dentist:", 1)
    dentist_var = tk.StringVar()
    dentist_combo = ttk.Combobox(
        body, textvariable=dentist_var, values=list(dentist_map),
        state="readonly", width=36
    )
    dentist_combo.grid(row=1, column=1, padx=5, pady=8, sticky="ew")
    dentist_combo.current(0)

    add_label("Requested Date:", 2)
    date_entry = tk.Entry(body, width=39)
    date_entry.grid(row=2, column=1, padx=5, pady=8, sticky="ew")
    date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))

    add_label("Preferred Start:", 3)
    start_entry = tk.Entry(body, width=39)
    start_entry.grid(row=3, column=1, padx=5, pady=8, sticky="ew")
    start_entry.insert(0, "10:30")

    add_label("Duration (minutes):", 4)
    duration_entry = tk.Entry(body, width=39)
    duration_entry.grid(row=4, column=1, padx=5, pady=8, sticky="ew")
    duration_entry.insert(0, "30")

    add_label("Next No. (requested date):", 5)
    appointment_number_var = tk.StringVar(value="—")
    tk.Label(
        body, textvariable=appointment_number_var,
        fg="#198754", font=("Arial", 11, "bold"), anchor="w"
    ).grid(row=5, column=1, padx=5, pady=8, sticky="w")

    add_label("Status:", 6)
    status_var = tk.StringVar()
    status_combo = ttk.Combobox(
        body, textvariable=status_var, values=list(status_map),
        state="readonly", width=36
    )
    status_combo.grid(row=6, column=1, padx=5, pady=8, sticky="ew")
    scheduled_status = next(
        (name for name in status_map if name.lower() == "scheduled"),
        next(iter(status_map))
    )
    status_var.set(scheduled_status)

    add_label("Reason (optional):", 7)
    reason_entry = tk.Entry(body, width=39)
    reason_entry.grid(row=7, column=1, padx=5, pady=8, sticky="ew")

    add_label("Notes (optional):", 8)
    notes_entry = tk.Entry(body, width=39)
    notes_entry.grid(row=8, column=1, padx=5, pady=8, sticky="ew")

    tk.Label(
        form,
        text="The system will move the booking forward if the dentist is busy.",
        fg="#555555", wraplength=500
    ).pack(pady=8)

    def refresh_appointment_number(*args):
        try:
            d = datetime.strptime(date_entry.get().strip(), "%Y-%m-%d").date()
            dentist_id = dentist_map.get(dentist_var.get())
            if not dentist_id:
                appointment_number_var.set("Select dentist")
                return
            with get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute("""
                    SELECT ISNULL(MAX(AppointmentNumber), 0) + 1
                    FROM dbo.Appointments
                    WHERE DentistID = ?
                      AND CONVERT(date, AppointmentStartDateTime) = ?
                """, dentist_id, d)
                appointment_number_var.set(str(cursor.fetchone()[0]))
        except ValueError:
            appointment_number_var.set("Enter date as YYYY-MM-DD")
        except pyodbc.Error:
            appointment_number_var.set("Unavailable")

    dentist_combo.bind("<<ComboboxSelected>>", refresh_appointment_number)
    date_entry.bind("<KeyRelease>", refresh_appointment_number)
    refresh_appointment_number()

    def save_booking():
        if not patient_var.get() or not dentist_var.get() or not status_var.get():
            messagebox.showwarning("Required", "Select patient, dentist, and status.", parent=form)
            return
        try:
            requested_start = datetime.strptime(
                date_entry.get().strip() + " " + start_entry.get().strip(),
                "%Y-%m-%d %H:%M"
            )
            duration_minutes = int(duration_entry.get().strip())
            if duration_minutes <= 0 or duration_minutes > 480:
                raise ValueError
        except ValueError:
            messagebox.showwarning(
                "Invalid input",
                "Enter date as YYYY-MM-DD, time as HH:MM, and duration from 1 to 480 minutes.",
                parent=form
            )
            return

        patient_id = patient_map[patient_var.get()]
        dentist_id = dentist_map[dentist_var.get()]
        status_id = status_map[status_var.get()]
        duration = timedelta(minutes=duration_minutes)

        try:
            with get_connection() as connection:
                cursor = connection.cursor()

                # One lock per dentist prevents two simultaneous bookings
                # from receiving the same daily number or time slot.
                lock_resource = f"DentalAppointment:Dentist:{dentist_id}"
                cursor.execute("""
                    DECLARE @result int;
                    EXEC @result = sp_getapplock
                        @Resource = ?,
                        @LockMode = 'Exclusive',
                        @LockOwner = 'Transaction',
                        @LockTimeout = 10000;
                    SELECT @result;
                """, lock_resource)
                if cursor.fetchone()[0] < 0:
                    raise RuntimeError("Could not reserve a slot. Please try again.")

                # Load this dentist's weekly schedule (Python weekday: Monday=0 ... Sunday=6).
                cursor.execute("""
                    SELECT DayOfWeek, IsActive, WorkStartTime, WorkEndTime
                    FROM dbo.DentistWorkingHours
                    WHERE DentistID = ? AND IsActive = 1
                """, dentist_id)
                weekly_schedule = {
                    row.DayOfWeek - 1: (row.WorkStartTime, row.WorkEndTime)
                    for row in cursor.fetchall()
                }
                if not weekly_schedule:
                    raise RuntimeError(
                        "No working hours are configured for this dentist. "
                        "Open Dentist Working Hours and set the working days and times."
                    )

                candidate_start = None
                candidate_end = None
                assigned = False

                # Search up to 180 calendar days, but only inside configured working hours.
                for day_offset in range(180):
                    current_date = requested_start.date() + timedelta(days=day_offset)
                    weekday = current_date.weekday()
                    if weekday not in weekly_schedule:
                        continue

                    opening_time, closing_time = weekly_schedule[weekday]
                    opening_dt = datetime.combine(current_date, opening_time)
                    closing_dt = datetime.combine(current_date, closing_time)

                    slot_start = max(
                        opening_dt,
                        requested_start if day_offset == 0 else opening_dt
                    )

                    while slot_start + duration <= closing_dt:
                        slot_end = slot_start + duration
                        cursor.execute("""
                            SELECT TOP 1 AppointmentStartDateTime,
                                         AppointmentEndDateTime
                            FROM dbo.Appointments
                            WHERE DentistID = ?
                              AND AppointmentStatusID NOT IN (4, 5)
                              AND AppointmentStartDateTime < ?
                              AND AppointmentEndDateTime > ?
                            ORDER BY AppointmentStartDateTime
                        """, dentist_id, slot_end, slot_start)
                        conflict = cursor.fetchone()

                        if not conflict:
                            candidate_start = slot_start
                            candidate_end = slot_end
                            assigned = True
                            break

                        # Try immediately after the conflicting appointment.
                        next_start = conflict.AppointmentEndDateTime
                        if next_start <= slot_start:
                            break
                        slot_start = next_start

                    if assigned:
                        break

                if not assigned:
                    raise RuntimeError(
                        "No available appointment slot was found in the dentist's "
                        "configured working hours during the next 180 days."
                    )

                # The daily sequence is based on the actual assigned date.
                cursor.execute("""
                    SELECT ISNULL(MAX(AppointmentNumber), 0) + 1
                    FROM dbo.Appointments
                    WHERE DentistID = ?
                      AND CONVERT(date, AppointmentStartDateTime) = ?
                """, dentist_id, candidate_start.date())
                appointment_number = cursor.fetchone()[0]

                cursor.execute("""
                    INSERT INTO dbo.Appointments
                        (PatientID, DentistID, AppointmentStatusID,
                         AppointmentStartDateTime, AppointmentEndDateTime,
                         AppointmentReason, AppointmentNotes, AppointmentNumber)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    patient_id, dentist_id, status_id,
                    candidate_start, candidate_end,
                    reason_entry.get().strip() or None,
                    notes_entry.get().strip() or None,
                    appointment_number
                )
                connection.commit()

            appointment_number_var.set(str(appointment_number))
            assigned_message = (
                f"Appointment booked successfully.\n"
                f"Appointment number: {appointment_number}\n"
                f"Assigned date: {candidate_start:%Y-%m-%d}\n"
                f"Assigned time: {candidate_start:%H:%M} - {candidate_end:%H:%M}"
            )
            messagebox.showinfo("Appointment Booked", assigned_message, parent=form)
            form.destroy()
            if on_saved:
                on_saved()

        except (pyodbc.Error, RuntimeError) as error:
            messagebox.showerror("Booking Error", str(error), parent=form)

    tk.Button(
        form, text="Find Next Available & Save", command=save_booking,
        bg="#198754", fg="white", width=27
    ).pack(pady=14)

def show_appointments():
    window = tk.Toplevel(root)
    window.title("Appointment Management")
    window.geometry("1250x650")

    tk.Label(window, text="Appointment Management",
             font=("Arial", 17, "bold")).pack(pady=12)

    search_frame = tk.Frame(window)
    search_frame.pack(fill="x", padx=15, pady=8)
    tk.Label(search_frame, text="Search:").pack(side="left")
    search_entry = tk.Entry(search_frame, width=35)
    search_entry.pack(side="left", padx=8)

    table_frame = tk.Frame(window)
    table_frame.pack(fill="both", expand=True, padx=15, pady=10)

    table = None
    display_columns = []

    def load_appointments():
        nonlocal table, display_columns
        try:
            with get_connection() as connection:
                cursor = connection.cursor()
                select_parts = [
                    "a.AppointmentNumber AS [Appointment No.]",
                    "a.AppointmentID AS [Appointment ID]",
                    "p.FirstName AS [Patient First Name]",
                    "p.LastName AS [Patient Last Name]",
                    "d.FirstName AS [Dentist First Name]",
                    "d.LastName AS [Dentist Last Name]",
                    "a.AppointmentStartDateTime AS [Start Date and Time]",
                    "a.AppointmentEndDateTime AS [End Date and Time]",
                    "st.StatusName AS [Status]",
                    "a.AppointmentReason AS [Reason]",
                    "a.AppointmentNotes AS [Notes]"
                ]
                query = """
                    SELECT {select}
                    FROM dbo.Appointments a
                    INNER JOIN dbo.Patients p ON a.PatientID = p.PatientID
                    INNER JOIN dbo.Dentists d ON a.DentistID = d.DentistID
                    INNER JOIN dbo.AppointmentStatuses st
                        ON a.AppointmentStatusID = st.AppointmentStatusID
                """.format(select=", ".join(select_parts))

                search_text = search_entry.get().strip()
                params = ()
                if search_text:
                    query += """
                        WHERE p.FirstName LIKE ? OR p.LastName LIKE ?
                           OR d.FirstName LIKE ? OR d.LastName LIKE ?
                           OR st.StatusName LIKE ?
                           OR CONVERT(NVARCHAR(30), a.AppointmentNumber) LIKE ?
                           OR CONVERT(NVARCHAR(30), a.AppointmentStartDateTime, 120) LIKE ?
                    """
                    like = f"%{search_text}%"
                    params = (like, like, like, like, like, like, like)

                query += """
                    ORDER BY a.AppointmentStartDateTime,
                             a.DentistID, a.AppointmentNumber
                """
                cursor.execute(query, params)
                rows = cursor.fetchall()
                headings = [desc[0] for desc in cursor.description]

                if table is None or headings != display_columns:
                    for widget in table_frame.winfo_children():
                        widget.destroy()
                    display_columns = headings
                    keys = [f"col{i}" for i in range(len(headings))]
                    table = ttk.Treeview(
                        table_frame, columns=keys, show="headings", height=18
                    )
                    widths = [95, 90, 125, 125, 125, 125, 170, 170, 100, 150, 180]
                    for key, heading, width in zip(keys, headings, widths):
                        table.heading(key, text=heading)
                        table.column(key, width=width, minwidth=80, anchor="center")
                    yscroll = ttk.Scrollbar(
                        table_frame, orient="vertical", command=table.yview
                    )
                    xscroll = ttk.Scrollbar(
                        table_frame, orient="horizontal", command=table.xview
                    )
                    table.configure(yscrollcommand=yscroll.set,
                                    xscrollcommand=xscroll.set)
                    table.grid(row=0, column=0, sticky="nsew")
                    yscroll.grid(row=0, column=1, sticky="ns")
                    xscroll.grid(row=1, column=0, sticky="ew")
                    table_frame.rowconfigure(0, weight=1)
                    table_frame.columnconfigure(0, weight=1)

                table.delete(*table.get_children())
                for row in rows:
                    table.insert(
                        "", "end",
                        values=tuple("" if value is None else str(value) for value in row)
                    )
        except pyodbc.Error as error:
            messagebox.showerror("Database Error", str(error), parent=window)

    tk.Button(search_frame, text="Search", command=load_appointments).pack(side="left")
    tk.Button(search_frame, text="Refresh", command=load_appointments).pack(side="left", padx=5)
    tk.Button(
        search_frame, text="New Appointment",
        command=lambda: create_appointment(load_appointments),
        bg="#198754", fg="white"
    ).pack(side="left", padx=8)
    search_entry.bind("<Return>", lambda event: load_appointments())
    load_appointments()

def show_dashboard():
    window = tk.Toplevel(root)
    window.title("Clinic Dashboard")
    window.geometry("650x420")
    window.resizable(False, False)

    tk.Label(window, text="Clinic Overview",
             font=("Arial", 18, "bold")).pack(pady=20)

    cards_frame = tk.Frame(window)
    cards_frame.pack(fill="both", expand=True, padx=25, pady=10)

    metrics = [
        ("Patients", "Patients"),
        ("Dentists", "Dentists"),
        ("Appointments", "Appointments"),
        ("Invoices", "Invoices")
    ]

    def refresh_dashboard():
        for widget in cards_frame.winfo_children():
            widget.destroy()

        try:
            counts = {}
            with get_connection() as connection:
                cursor = connection.cursor()
                for label, table_name in metrics:
                    cursor.execute(f"SELECT COUNT(*) FROM dbo.[{table_name}]")
                    counts[label] = cursor.fetchone()[0]

            for index, (label, table_name) in enumerate(metrics):
                card = tk.Frame(cards_frame, bg="#EAF2F8",
                                bd=1, relief="solid", padx=20, pady=18)
                card.grid(row=index // 2, column=index % 2,
                          padx=12, pady=12, sticky="nsew")
                tk.Label(card, text=label, bg="#EAF2F8",
                         font=("Arial", 12, "bold")).pack(pady=5)
                tk.Label(card, text=str(counts[label]), bg="#EAF2F8",
                         fg="#1976D2", font=("Arial", 24, "bold")).pack(pady=5)

            cards_frame.columnconfigure(0, weight=1)
            cards_frame.columnconfigure(1, weight=1)
            cards_frame.rowconfigure(0, weight=1)
            cards_frame.rowconfigure(1, weight=1)

        except pyodbc.Error as error:
            messagebox.showerror(
                "Dashboard Error",
                "Could not load all dashboard statistics.\\n\\n" + str(error),
                parent=window
            )

    tk.Button(window, text="Refresh", command=refresh_dashboard,
              width=16).pack(pady=12)

    refresh_dashboard()


# Main application window
root = tk.Tk()
root.title("Dental Practice Management")
root.geometry("1100x760")
root.minsize(900, 650)
root.resizable(True, True)
# Always open the main application maximized on Windows.
try:
    root.state("zoomed")
except tk.TclError:
    root.attributes("-fullscreen", True)

# Full-window dental background image using Tkinter's built-in GIF support.
# No third-party imaging library (such as Pillow) is required.
BACKGROUND_FILE = Path(__file__).resolve().parent / "dental_background.gif"
_background_photo = tk.PhotoImage(file=str(BACKGROUND_FILE))
_background_label = tk.Label(
    root, image=_background_photo, bd=0, highlightthickness=0
)
_background_label.place(x=0, y=0, relwidth=1, relheight=1)
_background_label.lower()

# Top navigation menu
menu_bar = tk.Frame(root, bg="#243447", padx=10, pady=10)
menu_bar.pack(side="top", fill="x")

def add_menu_button(text, command, color):
    tk.Button(
        menu_bar, text=text, command=command,
        bg=color, fg="white", activeforeground="white",
        font=("Arial", 9, "bold"), relief="flat",
        padx=12, pady=8, cursor="hand2"
    ).pack(side="left", padx=5)

add_menu_button("View Patients", show_patients, "#198754")
add_menu_button("Manage Dentists", show_dentists, "#6F42C1")
add_menu_button("Clinic Dashboard", show_dashboard, "#0D6E8A")
add_menu_button("Appointments", show_appointments, "#D97706")
add_menu_button("Dentist Working Hours", manage_dentist_working_hours, "#5B6C8F")

# Centered, polished registration card placed above the background image.
# A subtle outer frame creates a clean edge instead of the previous flat gray box.
registration_outer = tk.Frame(
    root, bg="#cbd5e1", bd=0, highlightthickness=0, padx=1, pady=1
)
registration_outer.pack(anchor="n", pady=(28, 20))

registration_card = tk.Frame(
    registration_outer, bg="#ffffff", bd=0, padx=34, pady=26
)
registration_card.pack()

registration_header = tk.Frame(registration_card, bg="#ffffff")
registration_header.pack(fill="x", pady=(0, 22))

tk.Label(
    registration_header, text="Dental Practice Management",
    bg="#ffffff", fg="#18324b",
    font=("Arial", 19, "bold")
).pack(pady=(0, 8))

tk.Label(
    registration_header, text="PATIENT REGISTRATION",
    bg="#ffffff", fg="#52708b",
    font=("Arial", 10, "bold")
).pack()

fields = [
    ("First Name", "first_name"),
    ("Last Name", "last_name"),
    ("National Code", "national_code"),
    ("Mobile Number", "mobile")
]
entries = {}

form_frame = tk.Frame(registration_card, bg="#ffffff")
form_frame.pack()
form_frame.grid_columnconfigure(0, minsize=145, weight=0)
form_frame.grid_columnconfigure(1, weight=1)

for row, (label_text, field_name) in enumerate(fields):
    tk.Label(
        form_frame, text=label_text, width=16, anchor="w",
        bg="#ffffff", fg="#263746",
        font=("Arial", 10, "bold")
    ).grid(row=row, column=0, sticky="w", padx=(0, 16), pady=10)

    entry = tk.Entry(
        form_frame, width=34, font=("Arial", 10),
        relief="solid", bd=1,
        highlightthickness=1, highlightbackground="#d5dde6",
        highlightcolor="#2878b8",
        insertbackground="#18324b"
    )
    entry.grid(row=row, column=1, sticky="ew", pady=10, ipady=5)
    entries[field_name] = entry

entry_first_name = entries["first_name"]
entry_last_name = entries["last_name"]
entry_national_code = entries["national_code"]
entry_mobile = entries["mobile"]

# Save button is centered directly below the input fields.
save_button = tk.Button(
    form_frame, text="Save Patient", command=save_patient,
    bg="#1769aa", fg="white", activebackground="#125487",
    activeforeground="white", font=("Arial", 10, "bold"),
    width=24, cursor="hand2", relief="flat", bd=0,
    pady=9
)
save_button.grid(
    row=len(fields), column=0, columnspan=2,
    pady=(22, 2), sticky="ew"
)

root.mainloop()
