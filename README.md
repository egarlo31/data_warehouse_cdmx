# Data Warehouse CDMX - Water Consumption Analysis

## Description

This project is a Data Warehouse focused on water consumption analysis in Mexico City (CDMX).
It integrates consumption and climate datasets using PostgreSQL, Docker, and a web interface for data visualization and consultation.

The system allows users to:

* Query water consumption information
* Visualize geographic data on an interactive map
* Filter by district, neighborhood, year, and bimester
* Access statistical summaries through APIs

---

## Technologies Used

* Python
* FastAPI
* PostgreSQL
* Docker
* HTML / CSS / JavaScript
* Git & GitHub

---

## Project Structure

```bash
data_warehouse_cdmx/
│
├── frontend/
│   ├── index.html
│   ├── login.html
│   └── Registro.html
│
├── data_warehouse_cdmx/
│   └── SQL scripts and database configuration
│
├── docker-compose.yml
├── main.py
└── README.md
```

---

## Features

* Dockerized PostgreSQL database
* REST API endpoints
* User login and registration system
* Interactive frontend
* Data filtering and visualization
* Geographic consultation using coordinates

---

## Installation

### Clone repository

```bash
git clone https://github.com/egarlo31/data_warehouse_cdmx.git
```

### Run Docker

```bash
docker compose up --build
```

### Run FastAPI

```bash
uvicorn main:app --reload
```

---

## API Example

```http
GET /api/consumo
GET /api/top-consumo
GET /api/consumo/resumen
```

---

## Authors
* Omar Fernando Pulido Morales
* Eduardo Uriel Velazquez Arrieta
* don comedias

