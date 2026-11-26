# University Research & Lab Asset Tracker

**Course:** INT1313 – Database Systems - PTITHCM

**Topic 4:** University Research & Lab Asset Tracker

**Team:** VibeCoderForData

---

## Members:

| Name | Student ID |
|---|---|
| Vo Dang Dung | N24DCCN112 |
| Pham Huynh Tuong Duy | N24DCCN115 |
| Nguyen Van Tien Dat (Lead) | N24DCCN104 |

## Overview

This Flask and MySQL application helps a university track research projects, lab assets, and the people who use them. Members can request equipment bookings and record lab visits. Operators review requests, and database rules check booking conflicts, stock quantities, expiry dates, and personnel certifications when materials are issued.

[Read the project report (PDF)](University%20Research%20%26%20Lab%20Asset%20Tracker.pdf)

## Project work

- [x] **1. Introduction and scope** — Defined the system objectives, data requirements, and business rules for research projects and laboratory operations.
- [x] **2.1 Conceptual design** — Modeled personnel, certifications, rooms, assets, and research activities. In the core EER, personnel roles can overlap, while each asset belongs to exactly one subtype. [EER diagram](EER_Data_Tuan3_4.drawio.png)
- [x] **2.2 Logical schema mapping** — Mapped the core EER to 17 relational tables and 23 foreign keys. The report explains composite keys and the shared primary keys used by subtypes. [Relational diagram](ERD.png)
- [x] **2.3 Normalization** — Documented functional dependencies, candidate keys, and the assumptions behind the 3NF and BCNF analysis.
- [x] **3. Data dictionary** — Documented column types, keys, nullability, defaults, and business constraints for the core tables.
- [x] **4.1 Database implementation** — Implemented the schema, indexes, views, triggers, stored procedures, and sample data. The integrated schema has 25 tables, including support for accounts and approvals. [SQL scripts](sql/)
- [x] **4.2 Queries and performance criteria** — Wrote 12 reporting queries covering project membership, valid certifications, bookings, inventory, maintenance, and room usage. The report defines a 200 ms search-response target. [Queries Q01–Q12](sql/07_truy_van.sql)
- [x] **5.1 Verification** — Added SQL and application test cases for constraints, booking approvals, registration, and access permissions. [Test suite](tests/)
- [x] **5.2 Access control** — Defined member and operator permissions in the application and granted the MySQL service account access to the tables, views, and procedures it uses. [Database grants](sql/05_cap_quyen.sql)

## Running the application

The project uses Python 3.11+ and MySQL 8.0.16+. The setup guide covers schema creation, sample data, database grants, and starting Flask. [Setup guide (Vietnamese)](HUONG_DAN_CHAY.txt)
