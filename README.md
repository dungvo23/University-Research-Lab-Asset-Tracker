# University Research & Lab Asset Tracker

**Course:** INT1313 – Database Systems

**Topic 4:** University Research & Lab Asset Tracker

**Team:** VibeCoderForData

---

## 👥 Team Members

| Name | Student ID |
|---|---|
| Vo Dang Dung | N24DCCN112 |
| Pham Huynh Tuong Duy | N24DCCN115 |
| Nguyen Van Tien Dat | N24DCCN104 |

## 📌 Project Status

🚧 **Planning Phase — Week 2 (WIP)**,
You can follow the report at [here](https://github.com/dungvo23/University-Research-Lab-Asset-Tracker/blob/main/University%20Research%20%26%20Lab%20Asset%20Tracker.pdf)

This project does not yet have a working implementation. The team is currently in the planning and design stage: requirements, business rules, and the conceptual data model have been drafted and are being refined.

---

## 📖 Overview

### Background

Academic institutions manage multiple laboratories, research projects, high-value equipment, and hazardous chemical materials.

### Problem Statement

Manual or spreadsheet-based management commonly leads to supply/material loss, scheduling conflicts over equipment usage, difficulty controlling project budgets, and safety risks when personnel without the appropriate certification access hazardous chemicals.

### System Objective

To design and build a normalized relational database system that manages personnel, certifications, research projects, funding sources, lab rooms, assets, and chemical materials/supplies — while enforcing safety, inventory, and usage-history constraints through database constraints and triggers at the implementation stage.



## 🗺️ Roadmap

| # | Section | Status |
|---|---|---|
| 1 | **Introduction & Project Scope** — System Objective, Business Rules & Constraints | ✅ Done |
| 2.1 | **Database Design** — Conceptual Model (ER/EER Diagram) | ✅ Done |
| 2.2 | **Database Design** — Logical Schema Mapping | 🔄 WIP |
| 2.3 | **Database Design** — Normalization Verification (1NF → 3NF/BCNF) | ⏳ Not started |
| 3 | **Data Dictionary** — Tables and attribute metadata | ⏳ Not started |
| 4.1 | **Database Implementation** — DDL Script (Tables, Views, Indexes, Triggers) | ⏳ Not started |
| 4.2 | **Database Implementation** — Advanced Queries & Performance Test Cases | ⏳ Not started |
| 5.1 | **Verification & Security** — Constraint test cases | ⏳ Not started |
| 5.2 | **Verification & Security** — RBAC definition (GRANT/REVOKE statements) | ⏳ Not started |

**Marked:** ✅ Done · 🔄 WIP · ⏳ Not started

---

## 📝 Notes

- Requirements are specified following **ISO/IEC/IEEE 29148** (superseding IEEE 830).
- The Conceptual Model and Data Dictionary will follow **ISO/IEC 19505 / IE Standards** and **ISO/IEC 11179**, respectively, per course guidelines.
- Specialization types have been explicitly defined for both supertypes:
  - `PERSONNEL` → overlapping, total
  - `LAB_ASSET` → disjoint, total
- Security requirements (RBAC, encryption) are defined at the requirements stage (NFR-01) but not yet implemented; implementation is scheduled for a later phase (Section 5.2 of the Roadmap).
- This README will be updated as the project progresses through each roadmap phase.
