# Real-Time Scalable Event Processing System with Auto-Scaling Simulation

## 👤 Author
Piyush Kumar  
M.Tech (Data Engineering)  
IIT Jodhpur  

---

## 📌 Project Overview

This project aims to design and implement a **real-time scalable event processing system** inspired by platforms like BookMyShow, where massive traffic spikes occur during ticket launches.

During such events:
- Thousands of users perform actions simultaneously
- Systems receive continuous streams of events
- Sudden load spikes (10x–100x) can crash traditional systems

This project simulates such scenarios and builds a system capable of:
- Processing events in real time
- Handling high data velocity
- Scaling dynamically based on load (in progress)

---

## 🚀 Current Progress (~40%)

### ✅ Completed
- Use case finalized (ticket booking system)
- System architecture designed
- Kafka and Zookeeper setup using Docker
- Producer implemented (event generator)
- Consumer implemented (event processing pipeline)

### ⏳ In Progress
- Auto-scaling module (dynamic worker management)
- Load-based performance evaluation

---

## 🧠 System Architecture (Current)

Producer → Kafka → Consumer → (Auto-Scaling Module - Upcoming)

---

## 🛠️ Tech Stack

- **Python**
- **Apache Kafka**
- **Zookeeper**
- **Docker**
- **VS Code**

---

## ⚙️ Why These Technologies?

### 🔹 Apache Kafka
Kafka is used as the core streaming platform because:
- It can handle **high-throughput real-time data**
- It acts as a **buffer between producers and consumers**
- It ensures **fault-tolerant and scalable event streaming**
- Widely used in industry (finance, booking systems, etc.)

---

### 🔹 Zookeeper
Zookeeper is required for Kafka because:
- It manages **Kafka cluster coordination**
- Keeps track of brokers and topics
- Ensures **system consistency and reliability**

---

### 🔹 Python
Python is used for:
- Rapid development
- Easy simulation of real-time events
- Strong ecosystem for data engineering tasks

---

### 🔹 Docker
Docker is used to:
- Run Kafka and Zookeeper easily
- Ensure **consistent environment setup**
- Avoid manual installation issues

---

## 📂 Project Structure
realtime-event-system/
│
├── producer/ # Generates booking events
├── consumer/ # Processes events
├── scaler/ # Auto-scaling logic (upcoming)
├── utils/ # Config and logging utilities
├── config/ # System settings
├── logs/ # Logs
├── docker-compose.yml


---

## 🔄 How It Works (Current Flow)

1. Producer generates booking events (search, booking, payment, etc.)
2. Events are sent to Kafka topic (`booking-events`)
3. Kafka stores and streams events
4. Consumer reads events in real time and processes them

---

## 🎯 Next Steps

- Implement multiple consumers (workers)
- Build auto-scaling module
- Simulate load increase (10x–100x)
- Measure latency and throughput
- Add monitoring (optional)

---

## 🔥 Key Learning Outcomes

- Real-time data streaming concepts
- Kafka-based event-driven architecture
- System design for scalability
- Distributed system fundamentals

---

## 📌 Note

This project is part of my **M.Tech Major Project** and is being developed incrementally, starting with a working streaming pipeline and progressing towards a fully scalable system.

## 🚧 Development Branch Active
This branch is used for implementing upcoming

## 📋 Development Checklist

### 🔹 Phase 1: Setup & Initial Pipeline
- [x] Project structure created
- [x] Kafka & Zookeeper setup using Docker
- [x] Kafka topic created (`booking-events`)
- [x] Producer implemented (event generator)
- [x] Consumer implemented (event processing)
- [x] Basic real-time streaming verified

---

### 🔹 Phase 2: Multi-Consumer System
- [ ] Implement multiple consumers (workers)
- [ ] Add worker identification and logging
- [ ] Validate parallel processing

---

### 🔹 Phase 3: Auto-Scaling Module
- [ ] Design auto-scaling strategy
- [ ] Implement scaling controller
- [ ] Dynamically spawn/terminate consumers
- [ ] Define scaling thresholds

---

### 🔹 Phase 4: Load Simulation
- [ ] Simulate high traffic (10x–100x)
- [ ] Measure throughput and latency
- [ ] Stress test system

---

### 🔹 Phase 5: Monitoring & Optimization
- [ ] Add logging system
- [ ] Integrate monitoring tools (optional)
- [ ] Optimize performance

---

### 🔹 Phase 6: Deployment & Finalization
- [ ] Prepare final architecture diagram
- [ ] Clean code and documentation
- [ ] Final testing and validation